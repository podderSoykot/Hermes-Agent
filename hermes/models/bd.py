"""Pydantic schemas for the BD agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str
    domain: str | None = None
    industry: str | None = None
    size: str | None = None
    location: str | None = None
    description: str | None = None
    pain_points: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    funding_stage: str | None = None
    research_notes: str | None = None
    created_at: datetime | None = None


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    company_id: str | None = None
    name: str
    title: str
    email: str | None = None
    linkedin: str | None = None
    decision_maker: bool = False
    influence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    subject: str
    body: str
    value_proposition: str | None = None
    call_to_action: str | None = None
    created_at: datetime | None = None


class FollowUpTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    proposal_id: str | None = None
    channel: str = "email"
    message: str
    scheduled_at: datetime
    status: str = "pending"
    sent_at: datetime | None = None


class MemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    entity_type: str
    entity_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class BDPipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(..., min_length=1)
    domain: str | None = None
    industry: str | None = None
    target_contact_title: str | None = None
    product_offering: str | None = None
    sender_name: str | None = None
    sender_company: str | None = None
    schedule_follow_up: bool = True


class AgentStepResult(BaseModel):
    agent: str
    status: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class BDPipelineResult(BaseModel):
    company: CompanyProfile
    contacts: list[Contact]
    proposal: Proposal
    follow_up: FollowUpTask | None = None
    steps: list[AgentStepResult] = Field(default_factory=list)
    crm_record_ids: dict[str, str] = Field(default_factory=dict)
