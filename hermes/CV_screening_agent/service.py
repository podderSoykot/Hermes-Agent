"""CV screening service."""

from __future__ import annotations

from hermes.CV_screening_agent.agent import CVScreeningAgent
from hermes.CV_screening_agent.models import CVScreeningRequest, CVScreeningResult
from hermes.db.session import get_session
from hermes.llm import LLMClient
from hermes.memory.store import MemoryStore


class CVScreeningService:
    def __init__(self) -> None:
        self.agent = CVScreeningAgent(LLMClient())

    def screen(self, request: CVScreeningRequest) -> CVScreeningResult:
        result = self.agent.screen(request)
        with get_session() as session:
            MemoryStore(session).remember(
                entity_type="cv_screening",
                content=f"CV score: {result.score}/100. {result.reason}",
                metadata={"score": result.score},
            )
        return result
