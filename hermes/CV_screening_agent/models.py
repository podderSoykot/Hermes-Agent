"""Pydantic models for CV screening."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CVScreeningRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_description: str = Field(..., min_length=10)
    cv_text: str = Field(..., min_length=20)


class CVScreeningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=100.0)
    reason: str = ""
    used_gpt: bool = False
