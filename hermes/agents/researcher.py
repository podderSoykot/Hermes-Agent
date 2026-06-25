"""Company research agent."""

from __future__ import annotations

from hermes.agents.base import AgentContext, AgentResult, BaseAgent
from hermes.models.bd import BDPipelineRequest, CompanyProfile


class ResearchAgent(BaseAgent):
    name = "researcher"

    def run(self, request: BDPipelineRequest, **_: object) -> AgentResult:
        profile = self._research_company(request)
        self.context.memory.remember(
            entity_type="company",
            entity_id=profile.id,
            content=(
                f"Researched {profile.name}: industry={profile.industry}, "
                f"pain_points={profile.pain_points}, tech={profile.tech_stack}"
            ),
            metadata={"agent": self.name, "domain": profile.domain},
        )
        return AgentResult(
            agent=self.name,
            status="completed",
            summary=f"Researched {profile.name}",
            data={"company": profile.model_dump()},
        )

    def _research_company(self, request: BDPipelineRequest) -> CompanyProfile:
        domain = request.domain or self._guess_domain(request.company_name)
        past = self.context.memory.recall(request.company_name, entity_type="company")

        if self.context.llm.available:
            return self._research_with_llm(request, domain, past)
        return self._research_with_heuristics(request, domain, past)

    def _research_with_llm(
        self,
        request: BDPipelineRequest,
        domain: str | None,
        past: list,
    ) -> CompanyProfile:
        memory_context = "\n".join(entry.content for entry in past[:3])
        payload = self.context.llm.complete_json(
            system=(
                "You are a B2B company research analyst. Return JSON with keys: "
                "name, domain, industry, size, location, description, pain_points "
                "(array), tech_stack (array), funding_stage, research_notes."
            ),
            user=(
                f"Research company: {request.company_name}\n"
                f"Domain hint: {domain or 'unknown'}\n"
                f"Industry hint: {request.industry or 'unknown'}\n"
                f"Prior memory:\n{memory_context or 'none'}"
            ),
        )
        return CompanyProfile(
            name=payload.get("name", request.company_name),
            domain=payload.get("domain", domain),
            industry=payload.get("industry", request.industry),
            size=payload.get("size"),
            location=payload.get("location"),
            description=payload.get("description"),
            pain_points=payload.get("pain_points", []),
            tech_stack=payload.get("tech_stack", []),
            funding_stage=payload.get("funding_stage"),
            research_notes=payload.get("research_notes"),
        )

    def _research_with_heuristics(
        self,
        request: BDPipelineRequest,
        domain: str | None,
        past: list,
    ) -> CompanyProfile:
        industry = request.industry or "Technology"
        notes = "Heuristic research profile generated without LLM."
        if past:
            notes += f" Recalled {len(past)} prior memory entries."

        pain_points = [
            "Manual outbound sales workflows",
            "Slow lead qualification",
            "Inconsistent follow-up",
        ]
        if industry.lower() in {"healthcare", "finance"}:
            pain_points.append("Strict compliance and audit requirements")

        return CompanyProfile(
            name=request.company_name,
            domain=domain,
            industry=industry,
            size="201-500 employees",
            location="United States",
            description=(
                f"{request.company_name} operates in {industry} and likely seeks "
                "efficiency gains through automation and AI-assisted workflows."
            ),
            pain_points=pain_points,
            tech_stack=["Salesforce", "HubSpot", "Slack", "Google Workspace"],
            funding_stage="Series B",
            research_notes=notes,
        )

    @staticmethod
    def _guess_domain(company_name: str) -> str:
        slug = company_name.lower().replace(" ", "").replace(",", "")
        return f"{slug}.com"
