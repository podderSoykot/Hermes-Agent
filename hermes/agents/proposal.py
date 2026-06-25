"""Personalized proposal generation agent."""

from __future__ import annotations

from hermes.agents.base import AgentResult, BaseAgent
from hermes.config import settings
from hermes.models.bd import BDPipelineRequest, CompanyProfile, Contact, Proposal


class ProposalAgent(BaseAgent):
    name = "proposal"

    def run(
        self,
        company: CompanyProfile,
        contact: Contact,
        request: BDPipelineRequest,
        **_: object,
    ) -> AgentResult:
        proposal = self._generate_proposal(company, contact, request)
        self.context.memory.remember(
            entity_type="proposal",
            entity_id=proposal.id,
            content=f"Proposal for {company.name} to {contact.name}: {proposal.subject}",
            metadata={"agent": self.name, "contact_id": contact.id},
        )
        return AgentResult(
            agent=self.name,
            status="completed",
            summary=f"Generated proposal: {proposal.subject}",
            data={"proposal": proposal.model_dump()},
        )

    def _generate_proposal(
        self,
        company: CompanyProfile,
        contact: Contact,
        request: BDPipelineRequest,
    ) -> Proposal:
        offering = request.product_offering or settings.default_product_offering
        sender = request.sender_name or settings.default_sender_name
        sender_company = request.sender_company or settings.default_sender_company

        if self.context.llm.available:
            return self._generate_with_llm(
                company, contact, offering, sender, sender_company
            )
        return self._generate_with_template(
            company, contact, offering, sender, sender_company
        )

    def _generate_with_llm(
        self,
        company: CompanyProfile,
        contact: Contact,
        offering: str,
        sender: str,
        sender_company: str,
    ) -> Proposal:
        payload = self.context.llm.complete_json(
            system=(
                "You write concise, personalized B2B proposals. Return JSON with "
                "subject, body, value_proposition, call_to_action."
            ),
            user=(
                f"Sender: {sender} at {sender_company}\n"
                f"Offering: {offering}\n"
                f"Company: {company.name} ({company.industry})\n"
                f"Pain points: {', '.join(company.pain_points)}\n"
                f"Contact: {contact.name}, {contact.title}\n"
                f"Description: {company.description}"
            ),
        )
        return Proposal(
            subject=payload["subject"],
            body=payload["body"],
            value_proposition=payload.get("value_proposition"),
            call_to_action=payload.get("call_to_action"),
        )

    def _generate_with_template(
        self,
        company: CompanyProfile,
        contact: Contact,
        offering: str,
        sender: str,
        sender_company: str,
    ) -> Proposal:
        pain = company.pain_points[0] if company.pain_points else "operational inefficiency"
        subject = f"Helping {company.name} solve {pain.lower()}"
        body = (
            f"Hi {contact.name},\n\n"
            f"I noticed {company.name} is scaling in {company.industry or 'your market'}. "
            f"Teams like yours often struggle with {pain.lower()}.\n\n"
            f"At {sender_company}, we provide {offering}. Based on our research, "
            f"we could help your team automate outreach, improve follow-up consistency, "
            f"and give {contact.title}s clearer pipeline visibility.\n\n"
            f"Would you be open to a 20-minute call next week to explore fit?\n\n"
            f"Best,\n{sender}"
        )
        return Proposal(
            subject=subject,
            body=body,
            value_proposition=f"Reduce {pain.lower()} with autonomous BD agents",
            call_to_action="Book a 20-minute discovery call",
        )
