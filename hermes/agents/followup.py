"""Follow-up automation agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hermes.agents.base import AgentResult, BaseAgent
from hermes.config import settings
from hermes.models.bd import CompanyProfile, Contact, FollowUpTask, Proposal


class FollowUpAgent(BaseAgent):
    name = "followup"

    def run(
        self,
        company: CompanyProfile,
        contact: Contact,
        proposal: Proposal,
        **_: object,
    ) -> AgentResult:
        follow_up = self._build_follow_up(company, contact, proposal)
        self.context.memory.remember(
            entity_type="follow_up",
            entity_id=follow_up.id,
            content=(
                f"Scheduled follow-up for {contact.name} at {company.name} "
                f"on {follow_up.scheduled_at.isoformat()}"
            ),
            metadata={"agent": self.name, "channel": follow_up.channel},
        )
        return AgentResult(
            agent=self.name,
            status="completed",
            summary=f"Scheduled follow-up on {follow_up.scheduled_at.date()}",
            data={"follow_up": follow_up.model_dump()},
        )

    def _build_follow_up(
        self,
        company: CompanyProfile,
        contact: Contact,
        proposal: Proposal,
    ) -> FollowUpTask:
        scheduled_at = datetime.now(timezone.utc) + timedelta(days=settings.follow_up_days)
        message = self._build_message(company, contact, proposal)
        return FollowUpTask(
            channel="email",
            message=message,
            scheduled_at=scheduled_at,
            status="pending",
        )

    def _build_message(
        self,
        company: CompanyProfile,
        contact: Contact,
        proposal: Proposal,
    ) -> str:
        if self.context.llm.available:
            return self.context.llm.complete(
                system="Write a short, friendly B2B follow-up email. Plain text only.",
                user=(
                    f"Follow up with {contact.name} at {company.name} about proposal: "
                    f"{proposal.subject}\n\nOriginal message:\n{proposal.body}"
                ),
                max_tokens=512,
            )
        return (
            f"Hi {contact.name},\n\n"
            f"Just following up on my note about {proposal.value_proposition or 'our offering'}. "
            f"Happy to share a quick demo tailored to {company.name}'s workflow.\n\n"
            f"Would {proposal.call_to_action or 'a brief call'} still work this week?\n\n"
            f"Best,\n{settings.default_sender_name}"
        )
