"""Nous Hermes agent client — runs prompts through hermes-agent (Nous Research)."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from hermes.config import settings

logger = logging.getLogger(__name__)

CODE_TOOLSETS: str | None = "terminal,file,code_execution,skills"


def _nous_home() -> Path:
    """Project-local Nous config dir (avoids patching ~/.hermes)."""
    return Path(__file__).resolve().parents[2] / ".hermes-nous"


def _ensure_nous_config() -> Path:
    """Ensure Nous Hermes config uses chat_completions for gpt-4o-mini.

    Nous auto-selects codex_responses for api.openai.com, which breaks
    gpt-4o-mini (HTTP 400: Encrypted content is not supported with this model).
    """
    home = _nous_home()
    config_path = home / "config.yaml"
    model = (settings.openai_model or "gpt-4o-mini").strip()
    desired = (
        "model:\n"
        f"  default: {model}\n"
        "  provider: openai-api\n"
        "  api_mode: chat_completions\n"
    )
    if not config_path.exists() or config_path.read_text(encoding="utf-8") != desired:
        home.mkdir(parents=True, exist_ok=True)
        config_path.write_text(desired, encoding="utf-8")
        logger.info("Wrote Nous Hermes config at %s", config_path)
    os.environ["HERMES_HOME"] = str(home)
    return home


class NousHermesClient:
    """Invoke Nous Hermes via the oneshot agent API (bypasses broken `hermes chat` cli import)."""

    def __init__(self) -> None:
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from hermes_cli.oneshot import _run_agent  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def configured(self) -> bool:
        key = (settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
        return self.available and bool(key)

    def run(self, prompt: str) -> str:
        if not self.available:
            raise RuntimeError(
                "Nous Hermes is not installed. Run: pip install 'hermes-agent[mcp]'"
            )

        self._apply_env()
        _ensure_nous_config()
        try:
            from hermes_cli.env_loader import load_hermes_dotenv

            load_hermes_dotenv()
        except ImportError:
            pass
        from hermes_cli.oneshot import _run_agent

        os.environ["HERMES_YOLO_MODE"] = "1"
        os.environ["HERMES_ACCEPT_HOOKS"] = "1"

        model = (settings.openai_model or "").strip() or None
        has_openai = bool((settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or "").strip())
        provider = "openai-api" if has_openai else None

        logger.info(
            "Running Nous Hermes code task (model=%s, provider=%s, toolsets=%s)",
            model,
            provider or "auto",
            CODE_TOOLSETS or "none",
        )
        response = _run_agent(
            prompt,
            model=model,
            provider=provider,
            toolsets=CODE_TOOLSETS,
            use_config_toolsets=False,
        )
        text = (response or "").strip()
        if not text:
            raise RuntimeError(
                "Nous Hermes returned an empty response. "
                "Check OPENAI_API_KEY or run `hermes setup` / `hermes model`."
            )
        return text

    def run_json(self, prompt: str) -> dict[str, Any]:
        return parse_json_response(self.run(prompt))

    @staticmethod
    def _apply_env() -> None:
        api_key = (settings.openai_api_key or "").strip()
        if api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = api_key
        model = (settings.openai_model or "").strip()
        if model:
            os.environ.setdefault("HERMES_INFERENCE_MODEL", model)


def parse_json_response(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Nous Hermes returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        return json.loads(fence.group(1))

    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        return json.loads(brace.group(0))

    raise ValueError(f"Nous Hermes response did not contain JSON: {text[:500]}")
