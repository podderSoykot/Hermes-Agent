"""Base agent types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from hermes.llm import LLMClient
from hermes.memory.store import MemoryStore


@dataclass
class AgentContext:
    llm: LLMClient
    memory: MemoryStore
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent: str
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    name: str

    def __init__(self, context: AgentContext) -> None:
        self.context = context

    @abstractmethod
    def run(self, **kwargs: Any) -> AgentResult:
        pass
