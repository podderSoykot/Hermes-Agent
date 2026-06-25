"""FastAPI REST API for Hermes BD Agent frontend."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from hermes.agent import get_harmis_state, harmis_agent
from hermes.config import settings
from hermes.integrations.crm.postgres_crm import PostgresCRM
from hermes.db.session import get_session
from hermes.models.bd import BDPipelineRequest, BDPipelineResult, CompanyProfile
from hermes.utils.input import normalize_pipeline_request
from hermes.workflows.bd_service import BDService
from hermes.llm import LLMClient
from hermes.CV_screening_agent.models import CVScreeningRequest, CVScreeningResult
from hermes.CV_screening_agent.parser import extract_cv_text
from hermes.CV_screening_agent.service import CVScreeningService
from hermes.code_agent.models import CodeCreateRequest, CodeCreateResult
from hermes.code_agent.nous_client import NousHermesClient
from hermes.code_agent.service import CodeCreatorService

app = FastAPI(title="Hermes BD Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineBody(BaseModel):
    company_name: str = Field(..., min_length=1)
    domain: str | None = None
    industry: str | None = None
    target_contact_title: str | None = None
    product_offering: str | None = None
    schedule_follow_up: bool = True


class ResearchBody(BaseModel):
    company_name: str = Field(..., min_length=1)
    domain: str | None = None
    industry: str | None = None


class HarmisBody(BaseModel):
    action: str = Field(..., min_length=1, max_length=200)


class CVScreenBody(BaseModel):
    job_description: str = Field(..., min_length=10)
    cv_text: str = Field(..., min_length=20)


class CodeCreateBody(BaseModel):
    command: str = Field(..., min_length=3, max_length=4000)
    language: str | None = None
    context: str | None = None
    read_paths: list[str] | None = None
    write_file: bool = False
    output_path: str | None = None
    run_tests: bool = False
    test_command: str | None = None
    max_fix_attempts: int = Field(default=2, ge=0, le=5)
    backend: str | None = None


def _service() -> BDService:
    """Fresh service per request so GPT key / env changes are picked up."""
    return BDService()


def _cv_service() -> CVScreeningService:
    return CVScreeningService()


def _code_service() -> CodeCreatorService:
    return CodeCreatorService()


@app.get("/api/health")
def health() -> dict:
    llm = LLMClient()
    nous = NousHermesClient()
    return {
        "status": "ok",
        "service": "hermes-bd-agent",
        "gpt_enabled": llm.available,
        "model": settings.openai_model if llm.available else None,
        "nous_hermes_installed": nous.available,
        "nous_hermes_configured": nous.configured(),
        "code_agent_backend": settings.code_agent_backend,
    }


@app.get("/api/stats")
def stats() -> dict:
    with get_session() as session:
        return PostgresCRM(session).count_rows()


@app.get("/api/companies")
def list_companies(limit: int = Query(default=50, ge=1, le=200)) -> list[CompanyProfile]:
    return _service().list_companies(limit=limit)


@app.get("/api/companies/{company_id}")
def get_company(company_id: str) -> dict:
    with get_session() as session:
        crm = PostgresCRM(session)
        company = crm.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return {
            "company": company,
            "contacts": crm.list_contacts(company_id),
            "proposals": crm.list_proposals(company_id),
            "follow_ups": [f for f in crm.list_follow_ups() if f.company_id == company_id],
        }


@app.post("/api/pipeline", response_model=BDPipelineResult)
def run_pipeline(body: PipelineBody) -> BDPipelineResult:
    try:
        request = normalize_pipeline_request(BDPipelineRequest(**body.model_dump()))
        return _service().run_pipeline(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/companies/research")
def research_company(body: ResearchBody) -> CompanyProfile:
    try:
        body_norm = normalize_pipeline_request(
            BDPipelineRequest(
                company_name=body.company_name,
                domain=body.domain,
                industry=body.industry,
                schedule_follow_up=False,
            )
        )
        return _service().research_company(
            body_norm.company_name,
            domain=body_norm.domain,
            industry=body_norm.industry,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/memory")
def recall_memory(q: str = Query(..., min_length=1), limit: int = Query(default=20, ge=1, le=100)):
    return _service().recall_memory(q, limit=limit)


@app.get("/api/follow-ups")
def list_follow_ups(pending_only: bool = False):
    with get_session() as session:
        return PostgresCRM(session).list_follow_ups(pending_only=pending_only)


@app.post("/api/follow-ups/process")
def process_follow_ups():
    return _service().process_due_follow_ups()


@app.get("/api/proposals")
def list_proposals():
    with get_session() as session:
        return PostgresCRM(session).list_proposals()


@app.post("/api/harmis")
def harmis_act(body: HarmisBody) -> dict:
    try:
        response = harmis_agent(body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    state = get_harmis_state()
    return {
        "response": response,
        "action_count": state.action_count,
        "last_action": state.last_action,
    }


@app.post("/api/cv/screen", response_model=CVScreeningResult)
def screen_cv(body: CVScreenBody) -> CVScreeningResult:
    try:
        return _cv_service().screen(CVScreeningRequest(**body.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/cv/screen/file", response_model=CVScreeningResult)
async def screen_cv_file(
    job_description: str = Form(..., min_length=10),
    cv_file: UploadFile = File(...),
) -> CVScreeningResult:
    try:
        data = await cv_file.read()
        cv_text = extract_cv_text(data, cv_file.filename or "cv.pdf")
        return _cv_service().screen(
            CVScreeningRequest(job_description=job_description, cv_text=cv_text)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/code", response_model=CodeCreateResult)
@app.post("/api/cv/code", response_model=CodeCreateResult)
def create_code(body: CodeCreateBody) -> CodeCreateResult:
    try:
        return _code_service().create_code(CodeCreateRequest(**body.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
