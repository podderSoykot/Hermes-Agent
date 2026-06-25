"""CV screening — score a CV against a job description."""

from __future__ import annotations

from hermes.CV_screening_agent.models import CVScreeningRequest, CVScreeningResult
from hermes.llm import LLMClient


class CVScreeningAgent:
    name = "cv_screener"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def screen(self, request: CVScreeningRequest) -> CVScreeningResult:
        if self.llm.available:
            return self._score_with_gpt(request)
        return self._score_with_heuristics(request)

    def _score_with_gpt(self, request: CVScreeningRequest) -> CVScreeningResult:
        payload = self.llm.complete_json(
            system=(
                "You score how well a CV matches a job description. "
                "Return JSON with exactly two keys: "
                "score (number 0-100, how good the fit is), "
                "reason (one short sentence explaining the score)."
            ),
            user=(
                f"Job:\n{request.job_description}\n\n"
                f"CV:\n{request.cv_text}"
            ),
        )
        return CVScreeningResult(
            score=min(100.0, max(0.0, float(payload.get("score", 0)))),
            reason=str(payload.get("reason", "")),
            used_gpt=True,
        )

    def _score_with_heuristics(self, request: CVScreeningRequest) -> CVScreeningResult:
        cv_words = {w.strip(".,()").lower() for w in request.cv_text.split() if len(w) > 3}
        job_words = {w.strip(".,()").lower() for w in request.job_description.split() if len(w) > 3}
        if not job_words:
            return CVScreeningResult(score=50.0, reason="No job keywords to compare.", used_gpt=False)

        overlap = len(cv_words & job_words)
        score = min(100.0, round(overlap / len(job_words) * 100, 1))
        return CVScreeningResult(
            score=score,
            reason=f"Keyword overlap: {overlap}/{len(job_words)} job terms found in CV.",
            used_gpt=False,
        )
