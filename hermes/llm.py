"""LLM helper — OpenAI GPT with template fallback when no API key."""

from __future__ import annotations

import json
import re

from hermes.config import settings


class LLMClient:
    """Thin wrapper around OpenAI Chat Completions."""

    def __init__(self) -> None:
        self._client = None
        api_key = (settings.openai_api_key or "").strip()
        if api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=api_key)
            except ImportError:
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, system: str, user: str, *, max_tokens: int = 2048) -> str:
        if self._client is None:
            return user
        response = self._client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content
        return (content or "").strip()

    def complete_json(self, system: str, user: str) -> dict:
        text = self.complete(
            system + "\nRespond with valid JSON only, no markdown fences.",
            user,
            max_tokens=4096,
        )
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
