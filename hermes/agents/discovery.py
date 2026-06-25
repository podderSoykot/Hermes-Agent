"""Decision-maker discovery agent."""

from __future__ import annotations

from hermes.agents.base import AgentResult, BaseAgent
from hermes.models.bd import BDPipelineRequest, CompanyProfile, Contact


DEFAULT_ROLES = [
    ("Chief Revenue Officer", 0.95),
    ("VP of Sales", 0.9),
    ("Head of Business Development", 0.88),
    ("Director of Partnerships", 0.82),
    ("VP of Operations", 0.75),
]


class DiscoveryAgent(BaseAgent):
    name = "discovery"

    def run(
        self,
        company: CompanyProfile,
        request: BDPipelineRequest,
        **_: object,
    ) -> AgentResult:
        contacts = self._discover_contacts(company, request)
        for contact in contacts:
            self.context.memory.remember(
                entity_type="contact",
                entity_id=contact.id,
                content=f"{contact.name} ({contact.title}) at {company.name}",
                metadata={
                    "agent": self.name,
                    "decision_maker": contact.decision_maker,
                    "influence_score": contact.influence_score,
                },
            )

        primary = next((c for c in contacts if c.decision_maker), contacts[0])
        return AgentResult(
            agent=self.name,
            status="completed",
            summary=f"Discovered {len(contacts)} decision-makers; primary: {primary.name}",
            data={
                "contacts": [contact.model_dump() for contact in contacts],
                "primary_contact": primary.model_dump(),
            },
        )

    def _discover_contacts(
        self,
        company: CompanyProfile,
        request: BDPipelineRequest,
    ) -> list[Contact]:
        if self.context.llm.available:
            return self._discover_with_llm(company, request)
        return self._discover_with_heuristics(company, request)

    def _discover_with_llm(
        self,
        company: CompanyProfile,
        request: BDPipelineRequest,
    ) -> list[Contact]:
        payload = self.context.llm.complete_json(
            system=(
                "You identify B2B decision makers. Return JSON with key 'contacts' "
                "as an array of objects: name, title, email, linkedin, decision_maker "
                "(bool), influence_score (0-1), notes."
            ),
            user=(
                f"Company: {company.name}\n"
                f"Industry: {company.industry}\n"
                f"Description: {company.description}\n"
                f"Target title hint: {request.target_contact_title or 'any economic buyer'}"
            ),
        )
        contacts = []
        for item in payload.get("contacts", [])[:5]:
            contacts.append(
                Contact(
                    name=item["name"],
                    title=item["title"],
                    email=item.get("email"),
                    linkedin=item.get("linkedin"),
                    decision_maker=bool(item.get("decision_maker", False)),
                    influence_score=float(item.get("influence_score", 0.5)),
                    notes=item.get("notes"),
                )
            )
        if contacts:
            return contacts
        return self._discover_with_heuristics(company, request)

    def _discover_with_heuristics(
        self,
        company: CompanyProfile,
        request: BDPipelineRequest,
    ) -> list[Contact]:
        slug = (company.domain or "company").split(".")[0]
        contacts: list[Contact] = []
        target = (request.target_contact_title or "").lower()

        for title, score in DEFAULT_ROLES:
            is_primary = target in title.lower() if target else score >= 0.88
            first = title.split()[-1].lower()
            contacts.append(
                Contact(
                    name=f"Alex {first.title()}",
                    title=title,
                    email=f"alex.{first}@{slug}.com",
                    linkedin=f"https://linkedin.com/in/alex-{first}-{slug}",
                    decision_maker=is_primary or score >= 0.88,
                    influence_score=score,
                    notes=f"Likely stakeholder for {company.industry} BD outreach.",
                )
            )
        return contacts[:3]
