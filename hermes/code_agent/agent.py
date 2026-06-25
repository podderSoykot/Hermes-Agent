"""Hermes code agent — Nous Hermes agent or OpenAI GPT pipeline."""

from __future__ import annotations

import logging
import re
import sys

from hermes.code_agent.analyzer import analyze_request, fix_code, review_code
from hermes.code_agent.filesystem import read_project_file, write_code_file
from hermes.code_agent.models import CodeCreateRequest, CodeCreateResult, PipelineStep
from hermes.code_agent.nous_client import NousHermesClient, parse_json_response
from hermes.code_agent.terminal import run_command
from hermes.config import settings
from hermes.llm import LLMClient

logger = logging.getLogger(__name__)


class CodeCreatorAgent:
    name = "code_creator"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.nous = NousHermesClient()

    def create(self, request: CodeCreateRequest) -> CodeCreateResult:
        backend = request.backend or settings.code_agent_backend
        if backend == "nous_hermes" and self.nous.configured():
            try:
                return self._create_with_nous_hermes(request)
            except Exception as exc:
                logger.warning("Nous Hermes code agent failed, falling back to OpenAI: %s", exc)
                steps = [
                    PipelineStep(
                        step="nous_hermes",
                        status="error",
                        detail=str(exc)[:500],
                    )
                ]
                if self.llm.available:
                    result = self._create_with_openai(request)
                    result.steps = steps + result.steps
                    return result
                raise ValueError(f"Nous Hermes failed ({exc}) and OpenAI is not configured.") from exc

        if backend == "nous_hermes" and not self.nous.configured():
            if not self.nous.available:
                logger.warning("hermes-agent not installed; using OpenAI code pipeline.")
            elif not self.llm.available:
                raise ValueError(
                    "Nous Hermes requires hermes-agent and OPENAI_API_KEY. "
                    "Install: pip install 'hermes-agent[mcp]'"
                )

        return self._create_with_openai(request)

    def _create_with_nous_hermes(self, request: CodeCreateRequest) -> CodeCreateResult:
        steps: list[PipelineStep] = [PipelineStep(step="nous_hermes", status="running", detail="Starting agent")]
        context = (request.context or "").strip()

        for path in request.read_paths or []:
            try:
                content = read_project_file(path)
                context = f"{context}\n\n--- {path} ---\n{content}".strip()
                steps.append(PipelineStep(step="filesystem", status="ok", detail=f"Read {path}"))
            except ValueError as exc:
                steps.append(PipelineStep(step="filesystem", status="error", detail=str(exc)))

        prompt = self._build_nous_prompt(request, context)
        raw = self.nous.run(prompt)
        steps.append(PipelineStep(step="nous_hermes", status="ok", detail="Agent completed"))

        try:
            payload = parse_json_response(raw)
        except ValueError:
            payload = {
                "language": request.language or "python",
                "filename": _default_filename(request.language or "python"),
                "code": _strip_fences(raw),
                "explanation": "Nous Hermes completed the task (response was not JSON).",
                "success": True,
            }

        language = str(payload.get("language", request.language or "python")).strip() or "python"
        filename = str(payload.get("filename", "")).strip() or _default_filename(language)
        code = _strip_fences(str(payload.get("code", "")))
        explanation = str(payload.get("explanation", "")).strip()
        written_path = payload.get("written_path")
        if written_path is not None:
            written_path = str(written_path).strip() or None
        test_output = payload.get("test_output")
        if test_output is not None:
            test_output = str(test_output).strip() or None
        success = bool(payload.get("success", True))

        if request.write_file and request.output_path and code and not written_path:
            written_path = write_code_file(request.output_path, code)
            steps.append(PipelineStep(step="filesystem", status="ok", detail=f"Wrote {written_path}"))

        return CodeCreateResult(
            language=language,
            filename=filename,
            code=code,
            explanation=explanation,
            written_path=written_path,
            analysis=str(payload.get("analysis", "")).strip() or None,
            test_output=test_output,
            success=success,
            steps=steps,
            used_gpt=False,
            used_nous_hermes=True,
            backend="nous_hermes",
        )

    def _create_with_openai(self, request: CodeCreateRequest) -> CodeCreateResult:
        if not self.llm.available:
            raise ValueError("OPENAI_API_KEY is required for the code agent.")

        steps: list[PipelineStep] = []
        context = (request.context or "").strip()

        for path in request.read_paths or []:
            try:
                content = read_project_file(path)
                context = f"{context}\n\n--- {path} ---\n{content}".strip()
                steps.append(PipelineStep(step="filesystem", status="ok", detail=f"Read {path}"))
            except ValueError as exc:
                steps.append(PipelineStep(step="filesystem", status="error", detail=str(exc)))

        analysis = analyze_request(self.llm, request.command, context)
        steps.append(PipelineStep(step="analyze", status="ok", detail=analysis[:500]))

        payload = self.llm.complete_json(
            system=(
                "You are a senior software engineer. Generate clean, runnable code from the user's command. "
                "Return JSON with exactly these keys: "
                "language (string), filename (string with extension), "
                "code (full source only — no markdown fences), "
                "explanation (one or two sentences)."
            ),
            user=self._build_prompt(request, context, analysis),
        )
        code = _strip_fences(str(payload.get("code", "")))
        language = str(payload.get("language", request.language or "python")).strip() or "python"
        filename = str(payload.get("filename", "")).strip() or _default_filename(language)
        explanation = str(payload.get("explanation", "")).strip()
        steps.append(PipelineStep(step="generate", status="ok", detail=f"Generated {filename}"))

        review = review_code(self.llm, request.command, code, language)
        steps.append(PipelineStep(step="analyze", status="ok", detail=f"Review: {review[:400]}"))

        written_path: str | None = None
        if request.write_file and request.output_path:
            written_path = write_code_file(request.output_path, code)
            steps.append(PipelineStep(step="filesystem", status="ok", detail=f"Wrote {written_path}"))

        test_output: str | None = None
        success = True
        if request.run_tests:
            test_cmd = request.test_command or _default_test_command(language, written_path, code)
            if test_cmd:
                for attempt in range(request.max_fix_attempts + 1):
                    result = run_command(test_cmd)
                    test_output = result.output
                    if result.returncode == 0:
                        steps.append(
                            PipelineStep(step="test", status="ok", detail=test_output[:500] or "Passed")
                        )
                        break

                    success = False
                    steps.append(
                        PipelineStep(
                            step="test",
                            status="error",
                            detail=test_output[:500] or f"Exit code {result.returncode}",
                        )
                    )
                    if attempt >= request.max_fix_attempts:
                        break

                    code, fix_note = fix_code(self.llm, request.command, code, test_output, language)
                    explanation = fix_note or explanation
                    steps.append(
                        PipelineStep(step="fix", status="ok", detail=f"Attempt {attempt + 1}: {fix_note}")
                    )
                    if written_path and request.output_path:
                        write_code_file(request.output_path, code)
            else:
                steps.append(PipelineStep(step="test", status="skipped", detail="No test command available"))

        return CodeCreateResult(
            language=language,
            filename=filename,
            code=code,
            explanation=explanation,
            written_path=written_path,
            analysis=analysis,
            test_output=test_output,
            success=success,
            steps=steps,
            used_gpt=True,
            used_nous_hermes=False,
            backend="openai",
        )

    def _build_nous_prompt(self, request: CodeCreateRequest, context: str) -> str:
        parts = [
            "You are the Hermes Code Agent (Nous Hermes). Complete this coding task using your "
            "terminal, file, and code_execution tools as needed.",
            "",
            f"Command:\n{request.command}",
        ]
        if request.language:
            parts.append(f"Preferred language: {request.language}")
        if context:
            parts.append(f"Context / existing code:\n{context[:12000]}")
        if request.write_file and request.output_path:
            parts.append(f"Save the final code to this project path: {request.output_path}")
        if request.run_tests:
            test_cmd = request.test_command or "(choose an appropriate test/compile command)"
            parts.append(f"Run tests after generation. Test command: {test_cmd}")
        parts.extend(
            [
                "",
                "When finished, respond with ONLY valid JSON (no markdown fences) using these keys:",
                "language, filename, code, explanation, written_path (or null), test_output (or null), "
                "success (boolean), analysis (optional short summary).",
            ]
        )
        return "\n".join(parts)

    def _build_prompt(self, request: CodeCreateRequest, context: str, analysis: str) -> str:
        parts = [
            f"Command:\n{request.command}",
            f"Analysis:\n{analysis}",
        ]
        if request.language:
            parts.append(f"Preferred language: {request.language}")
        if context:
            parts.append(f"Context:\n{context[:12000]}")
        return "\n\n".join(parts)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[\w-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _default_filename(language: str) -> str:
    ext = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "bash": "sh",
        "shell": "sh",
        "html": "html",
        "css": "css",
        "json": "json",
        "sql": "sql",
    }.get(language.lower(), "txt")
    return f"generated.{ext}"


def _default_test_command(language: str, written_path: str | None, code: str) -> str | None:
    py = sys.executable
    if written_path and language.lower() == "python":
        return f'"{py}" -m py_compile "{written_path}"'
    if language.lower() == "python" and code.strip():
        escaped = code.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{py}" -c "{escaped}"'
    return None
