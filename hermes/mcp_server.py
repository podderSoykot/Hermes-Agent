"""Hermes MCP server: Harmis persona + Autonomous BD Agent tools."""

from __future__ import annotations

import json
from enum import Enum

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from hermes.agent import get_harmis_state, harmis_agent
from hermes.models.bd import BDPipelineRequest
from hermes.workflows.bd_service import BDService
from hermes.CV_screening_agent.models import CVScreeningRequest
from hermes.CV_screening_agent.service import CVScreeningService

mcp = FastMCP(
    "hermes_mcp",
    instructions=(
        "Hermes Agent MCP server with two capabilities:\n"
        "1. Harmis persona tools (harmis_act, harmis_status)\n"
        "2. Autonomous Business Development Agent (bd_run_pipeline, bd_research_company, "
        "bd_discover_contacts, bd_generate_proposal, bd_recall_memory, bd_list_companies, "
        "bd_process_follow_ups)\n"
        "3. CV Screening (cv_screen) — score a CV against a job description\n\n"
        "BD data is stored in PostgreSQL. Use bd_run_pipeline for end-to-end outreach."
    ),
)

_bd_service: BDService | None = None
_cv_service: CVScreeningService | None = None


def _get_cv_service() -> CVScreeningService:
    global _cv_service
    if _cv_service is None:
        _cv_service = CVScreeningService()
    return _cv_service


def _get_bd_service() -> BDService:
    global _bd_service
    if _bd_service is None:
        _bd_service = BDService()
    return _bd_service


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


def _format_error(message: str) -> str:
    return f"Error: {message}"


def _render(data: object, fmt: ResponseFormat) -> str:
    if fmt == ResponseFormat.JSON:
        if hasattr(data, "model_dump"):
            return json.dumps(data.model_dump(mode="json"), indent=2, default=str)
        return json.dumps(data, indent=2, default=str)
    if hasattr(data, "model_dump"):
        payload = data.model_dump(mode="json")
    else:
        payload = data
    return _to_markdown(payload)


def _to_markdown(payload: object, title: str | None = None) -> str:
    if isinstance(payload, dict):
        lines = [f"# {title}", ""] if title else []
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                lines.append(f"## {key.replace('_', ' ').title()}")
                lines.append("```json")
                lines.append(json.dumps(value, indent=2, default=str))
                lines.append("```")
            else:
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        return "\n".join(lines)
    return str(payload)


# --- Harmis tools ---


class HarmisActInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action: str = Field(..., min_length=1, max_length=200)
    response_format: ResponseFormat = ResponseFormat.MARKDOWN

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Action cannot be empty.")
        return value.strip()


class HarmisStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


@mcp.tool(name="harmis_act")
async def harmis_act(params: HarmisActInput) -> str:
    """Ask Harmis to perform an action and return his response."""
    try:
        response = harmis_agent(params.action)
    except ValueError as exc:
        return _format_error(str(exc))
    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"action": params.action, "response": response}, indent=2)
    return response


@mcp.tool(name="harmis_status")
async def harmis_status(params: HarmisStatusInput) -> str:
    """Get Harmis's personality and current activity state."""
    state = get_harmis_state()
    payload = {
        "personality": "aggressive, energetic, ready for action",
        "action_count": state.action_count,
        "last_action": state.last_action,
        "last_response": state.last_response,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }
    return _render(payload, params.response_format)


# --- BD Agent tools ---


class BDRunPipelineInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(..., min_length=1)
    domain: str | None = None
    industry: str | None = None
    target_contact_title: str | None = None
    product_offering: str | None = None
    schedule_follow_up: bool = True
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


class BDResearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(..., min_length=1)
    domain: str | None = None
    industry: str | None = None
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


class BDDiscoverInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    target_contact_title: str | None = None
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


class BDProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    contact_id: str
    product_offering: str | None = None
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


class BDMemoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


class BDListCompaniesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


class BDProcessFollowUpsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


@mcp.tool(
    name="bd_run_pipeline",
    annotations={
        "title": "Run BD Pipeline",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def bd_run_pipeline(params: BDRunPipelineInput) -> str:
    """Run the full autonomous BD pipeline: research, discovery, proposal, CRM, follow-up.

    Orchestrates multi-agent workflow and persists results to PostgreSQL.
    """
    try:
        result = _get_bd_service().run_pipeline(
            BDPipelineRequest(
                company_name=params.company_name,
                domain=params.domain,
                industry=params.industry,
                target_contact_title=params.target_contact_title,
                product_offering=params.product_offering,
                schedule_follow_up=params.schedule_follow_up,
            )
        )
        return _render(result, params.response_format)
    except Exception as exc:
        return _format_error(str(exc))


@mcp.tool(name="bd_research_company")
async def bd_research_company(params: BDResearchInput) -> str:
    """Research a target company and save the profile to PostgreSQL CRM."""
    try:
        result = _get_bd_service().research_company(
            params.company_name,
            domain=params.domain,
            industry=params.industry,
        )
        return _render(result, params.response_format)
    except Exception as exc:
        return _format_error(str(exc))


@mcp.tool(name="bd_discover_contacts")
async def bd_discover_contacts(params: BDDiscoverInput) -> str:
    """Discover decision-makers for a company and save contacts to CRM."""
    try:
        contacts = _get_bd_service().discover_contacts(
            params.company_id,
            target_contact_title=params.target_contact_title,
        )
        payload = [c.model_dump(mode="json") for c in contacts]
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"contacts": payload}, indent=2, default=str)
        return _to_markdown({"contacts": payload}, title="Discovered Contacts")
    except Exception as exc:
        return _format_error(str(exc))


@mcp.tool(name="bd_generate_proposal")
async def bd_generate_proposal(params: BDProposalInput) -> str:
    """Generate a personalized proposal for a company contact."""
    try:
        proposal = _get_bd_service().generate_proposal(
            params.company_id,
            params.contact_id,
            product_offering=params.product_offering,
        )
        return _render(proposal, params.response_format)
    except Exception as exc:
        return _format_error(str(exc))


@mcp.tool(name="bd_recall_memory")
async def bd_recall_memory(params: BDMemoryInput) -> str:
    """Recall long-term agent memory from PostgreSQL using full-text search."""
    try:
        entries = _get_bd_service().recall_memory(params.query, limit=params.limit)
        payload = [e.model_dump(mode="json") for e in entries]
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"memories": payload}, indent=2, default=str)
        return _to_markdown({"memories": payload}, title="Memory Recall")
    except Exception as exc:
        return _format_error(str(exc))


@mcp.tool(name="bd_list_companies")
async def bd_list_companies(params: BDListCompaniesInput) -> str:
    """List companies stored in the PostgreSQL CRM."""
    try:
        companies = _get_bd_service().list_companies(limit=params.limit)
        payload = [c.model_dump(mode="json") for c in companies]
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"companies": payload}, indent=2, default=str)
        return _to_markdown({"companies": payload}, title="CRM Companies")
    except Exception as exc:
        return _format_error(str(exc))


@mcp.tool(name="bd_process_follow_ups")
async def bd_process_follow_ups(params: BDProcessFollowUpsInput) -> str:
    """Process due follow-up tasks and mark them as sent in CRM."""
    try:
        processed = _get_bd_service().process_due_follow_ups()
        payload = [f.model_dump(mode="json") for f in processed]
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"processed": payload}, indent=2, default=str)
        return _to_markdown({"processed": payload}, title="Processed Follow-ups")
    except Exception as exc:
        return _format_error(str(exc))


class CVScreenInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_description: str = Field(..., min_length=10)
    cv_text: str = Field(..., min_length=20)
    response_format: ResponseFormat = ResponseFormat.MARKDOWN


@mcp.tool(name="cv_screen")
async def cv_screen(params: CVScreenInput) -> str:
    """Score a CV against a job description (0-100)."""
    try:
        result = _get_cv_service().screen(
            CVScreeningRequest(
                job_description=params.job_description,
                cv_text=params.cv_text,
            )
        )
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result.model_dump(), indent=2)
        return f"**Score: {result.score}/100**\n\n{result.reason}"
    except Exception as exc:
        return _format_error(str(exc))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
