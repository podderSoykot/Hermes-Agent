"""Code creator service."""

from __future__ import annotations

from hermes.code_agent.agent import CodeCreatorAgent
from hermes.code_agent.models import CodeCreateRequest, CodeCreateResult
from hermes.db.session import get_session
from hermes.llm import LLMClient
from hermes.memory.store import MemoryStore


class CodeCreatorService:
    def __init__(self) -> None:
        self.agent = CodeCreatorAgent(LLMClient())

    def create_code(self, request: CodeCreateRequest) -> CodeCreateResult:
        result = self.agent.create(request)
        with get_session() as session:
            MemoryStore(session).remember(
                entity_type="code_creator",
                content=(
                    f"Code agent ({'ok' if result.success else 'failed'}): "
                    f"{result.language} {result.filename}. {result.explanation}"
                ),
                metadata={
                    "language": result.language,
                    "filename": result.filename,
                    "success": result.success,
                },
            )
        return result
