"""PostgreSQL CRM integration."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from hermes.db.models import (
    ActivityORM,
    CompanyORM,
    ContactORM,
    FollowUpORM,
    ProposalORM,
)
from hermes.models.bd import (
    CompanyProfile,
    Contact,
    FollowUpTask,
    Proposal,
)


class PostgresCRM:
    """CRM operations backed by PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_company(self, profile: CompanyProfile) -> CompanyProfile:
        row = None
        if profile.id:
            row = self._session.get(CompanyORM, profile.id)
        if row is None and profile.domain:
            row = self._session.scalars(
                select(CompanyORM).where(CompanyORM.domain == profile.domain)
            ).first()
        if row is None:
            row = self._session.scalars(
                select(CompanyORM).where(CompanyORM.name == profile.name)
            ).first()

        if row is None:
            row = CompanyORM(
                name=profile.name,
                domain=profile.domain,
                industry=profile.industry,
                size=profile.size,
                location=profile.location,
                description=profile.description,
                pain_points=profile.pain_points,
                tech_stack=profile.tech_stack,
                funding_stage=profile.funding_stage,
                research_notes=profile.research_notes,
            )
            self._session.add(row)
        else:
            row.name = profile.name
            row.domain = profile.domain or row.domain
            row.industry = profile.industry or row.industry
            row.size = profile.size or row.size
            row.location = profile.location or row.location
            row.description = profile.description or row.description
            row.pain_points = profile.pain_points or row.pain_points
            row.tech_stack = profile.tech_stack or row.tech_stack
            row.funding_stage = profile.funding_stage or row.funding_stage
            row.research_notes = profile.research_notes or row.research_notes
            row.updated_at = datetime.now(timezone.utc)

        self._session.flush()
        return self._company_to_schema(row)

    def add_contacts(self, company_id: str, contacts: list[Contact]) -> list[Contact]:
        saved: list[Contact] = []
        for contact in contacts:
            row = ContactORM(
                company_id=company_id,
                name=contact.name,
                title=contact.title,
                email=contact.email,
                linkedin=contact.linkedin,
                decision_maker=contact.decision_maker,
                influence_score=contact.influence_score,
                notes=contact.notes,
            )
            self._session.add(row)
            self._session.flush()
            saved.append(self._contact_to_schema(row))
        return saved

    def save_proposal(self, proposal: Proposal) -> Proposal:
        row = ProposalORM(
            company_id=proposal.company_id,
            contact_id=proposal.contact_id,
            subject=proposal.subject,
            body=proposal.body,
            value_proposition=proposal.value_proposition,
            call_to_action=proposal.call_to_action,
            status="draft",
        )
        self._session.add(row)
        self._session.flush()
        return self._proposal_to_schema(row)

    def schedule_follow_up(self, follow_up: FollowUpTask) -> FollowUpTask:
        row = FollowUpORM(
            company_id=follow_up.company_id,
            contact_id=follow_up.contact_id,
            proposal_id=follow_up.proposal_id,
            channel=follow_up.channel,
            message=follow_up.message,
            scheduled_at=follow_up.scheduled_at,
            status=follow_up.status,
        )
        self._session.add(row)
        self._session.flush()
        return self._follow_up_to_schema(row)

    def log_activity(
        self,
        company_id: str | None,
        activity_type: str,
        subject: str,
        details: dict | None = None,
    ) -> None:
        self._session.add(
            ActivityORM(
                company_id=company_id,
                activity_type=activity_type,
                subject=subject,
                details=details or {},
            )
        )

    def get_company(self, company_id: str) -> CompanyProfile | None:
        row = self._session.get(CompanyORM, company_id)
        return self._company_to_schema(row) if row else None

    def list_companies(self, limit: int = 20) -> list[CompanyProfile]:
        rows = self._session.scalars(
            select(CompanyORM).order_by(CompanyORM.updated_at.desc()).limit(limit)
        ).all()
        return [self._company_to_schema(row) for row in rows]

    def list_contacts(self, company_id: str) -> list[Contact]:
        rows = self._session.scalars(
            select(ContactORM)
            .where(ContactORM.company_id == company_id)
            .order_by(ContactORM.influence_score.desc())
        ).all()
        return [self._contact_to_schema(row) for row in rows]

    def list_proposals(self, company_id: str | None = None) -> list[Proposal]:
        stmt = select(ProposalORM).order_by(ProposalORM.created_at.desc())
        if company_id:
            stmt = stmt.where(ProposalORM.company_id == company_id)
        rows = self._session.scalars(stmt).all()
        return [self._proposal_to_schema(row) for row in rows]

    def list_follow_ups(self, *, pending_only: bool = False) -> list[FollowUpTask]:
        stmt = select(FollowUpORM).order_by(FollowUpORM.scheduled_at.asc())
        if pending_only:
            stmt = stmt.where(FollowUpORM.status == "pending")
        rows = self._session.scalars(stmt).all()
        return [self._follow_up_to_schema(row) for row in rows]

    def count_rows(self) -> dict[str, int]:
        from sqlalchemy import func

        return {
            "companies": self._session.scalar(select(func.count()).select_from(CompanyORM)) or 0,
            "contacts": self._session.scalar(select(func.count()).select_from(ContactORM)) or 0,
            "proposals": self._session.scalar(select(func.count()).select_from(ProposalORM)) or 0,
            "follow_ups": self._session.scalar(select(func.count()).select_from(FollowUpORM)) or 0,
            "pending_follow_ups": self._session.scalar(
                select(func.count())
                .select_from(FollowUpORM)
                .where(FollowUpORM.status == "pending")
            ) or 0,
        }

    def get_due_follow_ups(self, as_of: datetime | None = None) -> list[FollowUpTask]:
        now = as_of or datetime.now(timezone.utc)
        rows = self._session.scalars(
            select(FollowUpORM)
            .where(FollowUpORM.status == "pending", FollowUpORM.scheduled_at <= now)
            .order_by(FollowUpORM.scheduled_at.asc())
        ).all()
        return [self._follow_up_to_schema(row) for row in rows]

    def mark_follow_up_sent(self, follow_up_id: str) -> FollowUpTask | None:
        row = self._session.get(FollowUpORM, follow_up_id)
        if row is None:
            return None
        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._follow_up_to_schema(row)

    @staticmethod
    def _company_to_schema(row: CompanyORM) -> CompanyProfile:
        return CompanyProfile(
            id=row.id,
            name=row.name,
            domain=row.domain,
            industry=row.industry,
            size=row.size,
            location=row.location,
            description=row.description,
            pain_points=row.pain_points or [],
            tech_stack=row.tech_stack or [],
            funding_stage=row.funding_stage,
            research_notes=row.research_notes,
            created_at=row.created_at,
        )

    @staticmethod
    def _contact_to_schema(row: ContactORM) -> Contact:
        return Contact(
            id=row.id,
            company_id=row.company_id,
            name=row.name,
            title=row.title,
            email=row.email,
            linkedin=row.linkedin,
            decision_maker=row.decision_maker,
            influence_score=row.influence_score,
            notes=row.notes,
        )

    @staticmethod
    def _proposal_to_schema(row: ProposalORM) -> Proposal:
        return Proposal(
            id=row.id,
            company_id=row.company_id,
            contact_id=row.contact_id,
            subject=row.subject,
            body=row.body,
            value_proposition=row.value_proposition,
            call_to_action=row.call_to_action,
            created_at=row.created_at,
        )

    @staticmethod
    def _follow_up_to_schema(row: FollowUpORM) -> FollowUpTask:
        return FollowUpTask(
            id=row.id,
            company_id=row.company_id,
            contact_id=row.contact_id,
            proposal_id=row.proposal_id,
            channel=row.channel,
            message=row.message,
            scheduled_at=row.scheduled_at,
            status=row.status,
            sent_at=row.sent_at,
        )
