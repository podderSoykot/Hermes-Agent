"""Pydantic models for the code agent pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str
    status: str
    detail: str = ""


class CodeCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    command: str = Field(..., min_length=3, max_length=4000)
    language: str | None = Field(default=None, max_length=50)
    context: str | None = Field(default=None, max_length=20000)
    read_paths: list[str] | None = Field(default=None, max_length=10)
    write_file: bool = False
    output_path: str | None = Field(default=None, max_length=500)
    run_tests: bool = False
    test_command: str | None = Field(default=None, max_length=500)
    max_fix_attempts: int = Field(default=2, ge=0, le=5)
    backend: Literal["nous_hermes", "openai"] | None = None


class CodeCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str
    filename: str
    code: str
    explanation: str = ""
    written_path: str | None = None
    analysis: str | None = None
    test_output: str | None = None
    success: bool = True
    steps: list[PipelineStep] = Field(default_factory=list)
    used_gpt: bool = False
    used_nous_hermes: bool = False
    backend: str = "openai"
