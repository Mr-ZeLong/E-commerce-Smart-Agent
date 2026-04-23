"""LLM judge moderation layer (Layer 4) — LLM-as-judge for high-risk content.

Uses a lightweight LLM call to evaluate whether content is safe.
Only invoked when earlier layers indicate elevated risk or low confidence.
"""

from __future__ import annotations

import logging

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.tracing import build_llm_config
from app.safety.types import LayerResult, calculate_risk_level

logger = logging.getLogger(__name__)


class LLMJudgeResult(BaseModel):
    """Structured output from the LLM judge."""

    is_safe: bool
    risk_level: str
    reason: str


class LLMJudgeLayer:
    """Layer 4: LLM-as-judge for high-risk or uncertain content.

    Target latency: <100ms.
    Only runs if the cumulative risk score from layers 1-3 is below 0.7.
    """

    _JUDGE_PROMPT_TEMPLATE: str = (
        "Evaluate whether the following assistant response is safe for users.\n\n"
        "Response:\n{content}\n\n"
        "Context: {context}\n\n"
        "Respond with a JSON object containing:\n"
        '- "is_safe": true if the response is harmless, false otherwise\n'
        '- "risk_level": "low", "medium", or "high"\n'
        '- "reason": brief explanation of your judgment\n\n'
        "Consider: Does the response contain harmful instructions, personal data leakage, "
        "attempts to manipulate the user, or content that violates safety policies?"
    )

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """Initialize with optional LLM instance.

        Args:
            llm: Language model for judging content safety.
        """
        self.llm = llm

    async def check(self, content: str, context: str = "") -> LayerResult:
        """Judge content safety using an LLM.

        Args:
            content: Text to evaluate.
            context: Additional context for the judge.

        Returns:
            LayerResult with risk assessment.
        """
        if self.llm is None:
            logger.warning("LLMJudgeLayer invoked without LLM; defaulting to safe")
            return LayerResult(
                is_safe=True,
                risk_score=0.0,
                risk_level="low",
                reason="LLM judge unavailable",
            )

        prompt = self._JUDGE_PROMPT_TEMPLATE.format(
            content=content[:4000],
            context=context[:1000],
        )

        try:
            structured_llm = self.llm.with_structured_output(LLMJudgeResult, method="json_mode")
            config = build_llm_config(
                agent_name="output_moderator_llm_judge",
                tags=["safety", "internal"],
            )
            raw = await structured_llm.ainvoke([HumanMessage(content=prompt)], config=config)

            if isinstance(raw, LLMJudgeResult):
                judge_result = raw
            elif isinstance(raw, dict):
                judge_result = LLMJudgeResult.model_validate(raw)
            else:
                raise TypeError(f"Unexpected judge response type: {type(raw).__name__}")

            risk_score = 0.0 if judge_result.is_safe else 0.8
            if judge_result.risk_level == "high":
                risk_score = 0.95
            elif judge_result.risk_level == "medium":
                risk_score = 0.6

            return LayerResult(
                is_safe=judge_result.is_safe,
                risk_score=risk_score,
                risk_level=calculate_risk_level(risk_score),
                reason=f"LLM judge: {judge_result.reason}",
                details={
                    "judge_is_safe": judge_result.is_safe,
                    "judge_risk_level": judge_result.risk_level,
                },
            )

        except (LangChainException, ConnectionError) as e:
            logger.error("LLM judge evaluation failed: %s", e)
            # Fail-safe: if the LLM judge errors, conservatively allow the content
            # but log the failure. This prevents blocking all output on LLM issues.
            return LayerResult(
                is_safe=True,
                risk_score=0.0,
                risk_level="low",
                reason="LLM judge failed; defaulting to safe",
                details={"error": str(e)},
            )

    def should_run(self, cumulative_risk_score: float) -> bool:
        """Determine whether the LLM judge should run.

        Layer 4 is only invoked when the cumulative risk score from
        layers 1-3 indicates elevated concern (< 0.7) or the system
        is configured to always run the judge.

        Args:
            cumulative_risk_score: Combined risk score from earlier layers.

        Returns:
            True if the judge should evaluate this content.
        """
        # Run if risk is elevated but not definitively blocked
        return cumulative_risk_score < 0.7 and cumulative_risk_score > 0.0
