"""Multi-agent orchestrator for BD pipeline."""

from __future__ import annotations

from hermes.agents.base import AgentContext, AgentResult
from hermes.agents.discovery import DiscoveryAgent
from hermes.agents.followup import FollowUpAgent
from hermes.agents.proposal import ProposalAgent
from hermes.agents.researcher import ResearchAgent
from hermes.integrations.crm.postgres_crm import PostgresCRM
from hermes.models.bd import (
    AgentStepResult,
    BDPipelineRequest,
    BDPipelineResult,
    CompanyProfile,
    Contact,
    FollowUpTask,
    Proposal,
)


class BDOrchestrator:
    """Orchestrator-workers pattern for autonomous business development."""

    def __init__(self, context: AgentContext, crm: PostgresCRM) -> None:
        self.context = context
        self.crm = crm
        self.researcher = ResearchAgent(context)
        self.discovery = DiscoveryAgent(context)
        self.proposal_agent = ProposalAgent(context)
        self.followup_agent = FollowUpAgent(context)

    def run_pipeline(self, request: BDPipelineRequest) -> BDPipelineResult:
        steps: list[AgentResult] = []

        research = self.researcher.run(request=request)
        steps.append(research)
        company = CompanyProfile.model_validate(research.data["company"])

        discovery = self.discovery.run(company=company, request=request)
        steps.append(discovery)
        contacts = [Contact.model_validate(item) for item in discovery.data["contacts"]]
        primary = Contact.model_validate(discovery.data["primary_contact"])

        proposal_result = self.proposal_agent.run(
            company=company,
            contact=primary,
            request=request,
        )
        steps.append(proposal_result)
        proposal = Proposal.model_validate(proposal_result.data["proposal"])

        follow_up: FollowUpTask | None = None
        if request.schedule_follow_up:
            followup_result = self.followup_agent.run(
                company=company,
                contact=primary,
                proposal=proposal,
            )
            steps.append(followup_result)
            follow_up = FollowUpTask.model_validate(followup_result.data["follow_up"])

        crm_ids = self._persist_to_crm(company, contacts, proposal, follow_up)
        company = self.crm.get_company(crm_ids["company_id"]) or company

        self.crm.log_activity(
            company_id=crm_ids["company_id"],
            activity_type="bd_pipeline_completed",
            subject=f"BD pipeline completed for {company.name}",
            details={
                "contacts_found": len(contacts),
                "proposal_id": crm_ids.get("proposal_id"),
                "follow_up_id": crm_ids.get("follow_up_id"),
            },
        )

        return BDPipelineResult(
            company=company,
            contacts=contacts,
            proposal=proposal,
            follow_up=follow_up,
            steps=[self._to_step(step) for step in steps],
            crm_record_ids=crm_ids,
        )

    def _persist_to_crm(
        self,
        company: CompanyProfile,
        contacts: list[Contact],
        proposal: Proposal,
        follow_up: FollowUpTask | None,
    ) -> dict[str, str]:
        saved_company = self.crm.upsert_company(company)
        saved_contacts = self.crm.add_contacts(saved_company.id, contacts)

        primary = next(
            (c for c in saved_contacts if c.decision_maker),
            saved_contacts[0],
        )
        proposal.company_id = saved_company.id
        proposal.contact_id = primary.id
        saved_proposal = self.crm.save_proposal(proposal)

        ids = {
            "company_id": saved_company.id,
            "primary_contact_id": primary.id,
            "proposal_id": saved_proposal.id,
        }

        if follow_up is not None:
            follow_up.company_id = saved_company.id
            follow_up.contact_id = primary.id
            follow_up.proposal_id = saved_proposal.id
            saved_follow_up = self.crm.schedule_follow_up(follow_up)
            ids["follow_up_id"] = saved_follow_up.id

        return ids

    @staticmethod
    def _to_step(result: AgentResult) -> AgentStepResult:
        return AgentStepResult(
            agent=result.agent,
            status=result.status,
            summary=result.summary,
            data=result.data,
        )
