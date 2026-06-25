"""BD workflow service layer."""

from __future__ import annotations

from datetime import datetime, timezone

from hermes.agents.base import AgentContext
from hermes.agents.orchestrator import BDOrchestrator
from hermes.db.models import ContactORM
from hermes.db.session import get_session, init_db
from hermes.integrations.crm.postgres_crm import PostgresCRM
from hermes.llm import LLMClient
from hermes.memory.store import MemoryStore
from hermes.models.bd import (
    BDPipelineRequest,
    BDPipelineResult,
    CompanyProfile,
    Contact,
    FollowUpTask,
    MemoryEntry,
    Proposal,
)


class BDService:
    """High-level API used by MCP tools and CLI."""

    def __init__(self) -> None:
        init_db()
        self.llm = LLMClient()

    def run_pipeline(self, request: BDPipelineRequest) -> BDPipelineResult:
        with get_session() as session:
            context = AgentContext(
                llm=self.llm,
                memory=MemoryStore(session),
            )
            orchestrator = BDOrchestrator(context, PostgresCRM(session))
            return orchestrator.run_pipeline(request)

    def research_company(
        self,
        company_name: str,
        *,
        domain: str | None = None,
        industry: str | None = None,
    ) -> CompanyProfile:
        from hermes.agents.researcher import ResearchAgent

        request = BDPipelineRequest(
            company_name=company_name,
            domain=domain,
            industry=industry,
            schedule_follow_up=False,
        )
        with get_session() as session:
            context = AgentContext(llm=self.llm, memory=MemoryStore(session))
            result = ResearchAgent(context).run(request=request)
            profile = CompanyProfile.model_validate(result.data["company"])
            saved = PostgresCRM(session).upsert_company(profile)
            return saved

    def discover_contacts(
        self,
        company_id: str,
        *,
        target_contact_title: str | None = None,
    ) -> list[Contact]:
        from hermes.agents.discovery import DiscoveryAgent

        with get_session() as session:
            crm = PostgresCRM(session)
            company = crm.get_company(company_id)
            if company is None:
                raise ValueError(f"Company not found: {company_id}")

            request = BDPipelineRequest(
                company_name=company.name,
                domain=company.domain,
                industry=company.industry,
                target_contact_title=target_contact_title,
                schedule_follow_up=False,
            )
            context = AgentContext(llm=self.llm, memory=MemoryStore(session))
            result = DiscoveryAgent(context).run(company=company, request=request)
            contacts = [
                Contact.model_validate(item) for item in result.data["contacts"]
            ]
            return crm.add_contacts(company_id, contacts)

    def generate_proposal(
        self,
        company_id: str,
        contact_id: str,
        *,
        product_offering: str | None = None,
    ) -> Proposal:
        from hermes.agents.proposal import ProposalAgent

        with get_session() as session:
            crm = PostgresCRM(session)
            company = crm.get_company(company_id)
            if company is None:
                raise ValueError(f"Company not found: {company_id}")

            contact_row = session.get(ContactORM, contact_id)
            if contact_row is None:
                raise ValueError(f"Contact not found: {contact_id}")

            contact = PostgresCRM._contact_to_schema(contact_row)
            request = BDPipelineRequest(
                company_name=company.name,
                product_offering=product_offering,
                schedule_follow_up=False,
            )
            context = AgentContext(llm=self.llm, memory=MemoryStore(session))
            result = ProposalAgent(context).run(
                company=company,
                contact=contact,
                request=request,
            )
            proposal = Proposal.model_validate(result.data["proposal"])
            proposal.company_id = company_id
            proposal.contact_id = contact_id
            return crm.save_proposal(proposal)

    def recall_memory(self, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        with get_session() as session:
            return MemoryStore(session).recall(query, limit=limit)

    def list_companies(self, limit: int = 20) -> list[CompanyProfile]:
        with get_session() as session:
            return PostgresCRM(session).list_companies(limit=limit)

    def process_due_follow_ups(self) -> list[FollowUpTask]:
        with get_session() as session:
            crm = PostgresCRM(session)
            due = crm.get_due_follow_ups(datetime.now(timezone.utc))
            processed: list[FollowUpTask] = []
            for task in due:
                processed.append(crm.mark_follow_up_sent(task.id))
                crm.log_activity(
                    company_id=task.company_id,
                    activity_type="follow_up_sent",
                    subject="Automated follow-up sent",
                    details={"follow_up_id": task.id, "channel": task.channel},
                )
            return processed
