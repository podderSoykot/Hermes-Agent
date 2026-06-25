"""LLM-backed code analysis."""

from __future__ import annotations

from hermes.llm import LLMClient


def analyze_request(llm: LLMClient, command: str, context: str) -> str:
    user = f"User request:\n{command}"
    if context.strip():
        user += f"\n\nExisting code / context:\n{context[:12000]}"
    return llm.complete(
        system=(
            "You are a code analyst. Briefly describe what needs to be built or changed, "
            "key files/functions involved, risks, and a short test strategy. "
            "Keep the answer under 8 sentences."
        ),
        user=user,
        max_tokens=512,
    )


def review_code(llm: LLMClient, command: str, code: str, language: str) -> str:
    return llm.complete(
        system=(
            "Review the generated code for correctness and completeness relative to the request. "
            "Note missing imports, edge cases, or obvious bugs in 3-5 bullet points."
        ),
        user=f"Request:\n{command}\n\nLanguage: {language}\n\nCode:\n{code[:8000]}",
        max_tokens=512,
    )


def fix_code(llm: LLMClient, command: str, code: str, test_output: str, language: str) -> tuple[str, str]:
    payload = llm.complete_json(
        system=(
            "Fix the code based on the test/runtime failure. "
            "Return JSON with keys: code (full fixed source, no markdown fences), "
            "explanation (one sentence on what you fixed)."
        ),
        user=(
            f"Original request:\n{command}\n\n"
            f"Language: {language}\n\n"
            f"Current code:\n{code}\n\n"
            f"Failure output:\n{test_output[:6000]}"
        ),
    )
    explanation = str(payload.get("explanation", "")).strip()
    fixed = str(payload.get("code", "")).strip()
    return fixed or code, explanation
