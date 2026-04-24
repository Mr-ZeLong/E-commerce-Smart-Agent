"""Output moderator orchestrator.

Coordinates the 4-layer moderation pipeline:
1. Rule-based (PII, keywords)
2. Regex patterns (injection, code)
3. Embedding similarity (semantic)
4. LLM judge (high-confidence arbiter)
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.observability.metrics import record_injection_attempt, record_safety_block
from app.retrieval.embeddings import QwenEmbeddings
from app.safety.embeddings import EmbeddingSimilarityLayer
from app.safety.llm_judge import LLMJudgeLayer
from app.safety.patterns import RegexPatternLayer
from app.safety.rules import RuleBasedLayer
from app.safety.types import LayerResult, ModerationResult, calculate_risk_level

logger = logging.getLogger(__name__)

_BLOCK_MESSAGE: str = (
    "[系统提示] 当前回复因包含潜在敏感信息或不合规内容已被过滤。如有疑问，请联系人工客服。"
)


class OutputModerator:
    """Orchestrates the 4-layer output moderation pipeline.

    Runs layers 1-3 sequentially for low latency. Layer 4 (LLM judge)
    is invoked conditionally when earlier layers show elevated risk
    but fall short of definitive blocking.
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        embedding_model: QwenEmbeddings | None = None,
        block_message: str | None = None,
    ) -> None:
        """Initialize moderation layers.

        Args:
            llm: Optional LLM for Layer 4 judge.
            embedding_model: Optional embedding model for Layer 3.
            block_message: Custom message shown when content is blocked.
        """
        self.layer1 = RuleBasedLayer()
        self.layer2 = RegexPatternLayer()
        self.layer3 = EmbeddingSimilarityLayer(embedding_model=embedding_model)
        self.layer4 = LLMJudgeLayer(llm=llm)
        self.block_message = block_message or _BLOCK_MESSAGE

    @staticmethod
    def _combine_risk_scores(layer_results: list[LayerResult]) -> float:
        """Combine layer risk scores using max with a small additive boost.

        Uses max(score) + 0.05 * count of non-zero scores, capped at 1.0.
        """
        scores = [r.risk_score for r in layer_results]
        if not scores:
            return 0.0
        max_score = max(scores)
        non_zero_count = sum(1 for s in scores if s > 0.0)
        combined = min(1.0, max_score + 0.05 * non_zero_count)
        return combined

    async def moderate(self, content: str, context: str = "") -> ModerationResult:
        """Run the moderation pipeline on content.

        Args:
            content: Agent response text to moderate.
            context: Optional context for the LLM judge.

        Returns:
            ModerationResult with safety decision and optional replacement text.
        """
        if not content or len(content.strip()) == 0:
            return ModerationResult(
                is_safe=True,
                risk_score=0.0,
                risk_level="low",
                reason="Empty content",
            )

        layer_results: dict[str, LayerResult] = {}

        # Layer 1: Rule-based
        result1 = self.layer1.check(content)
        layer_results["rule_based"] = result1
        if not result1.is_safe:
            logger.info("Layer 1 blocked content: %s", result1.reason)
            record_safety_block("rule_based", result1.reason or "blocked")
            return ModerationResult(
                is_safe=False,
                risk_score=result1.risk_score,
                risk_level=result1.risk_level,
                blocked_by_layer=1,
                replacement_text=self.block_message,
                reason=result1.reason or "Blocked by rule-based layer",
                layer_results=layer_results,
            )

        # Layer 2: Regex patterns
        result2 = self.layer2.check(content)
        layer_results["regex_patterns"] = result2
        if not result2.is_safe:
            logger.info("Layer 2 blocked content: %s", result2.reason)
            record_safety_block("regex_patterns", result2.reason or "blocked")
            if result2.details and result2.details.get("injection"):
                record_injection_attempt()
            return ModerationResult(
                is_safe=False,
                risk_score=result2.risk_score,
                risk_level=result2.risk_level,
                blocked_by_layer=2,
                replacement_text=self.block_message,
                reason=result2.reason or "Blocked by regex pattern layer",
                layer_results=layer_results,
            )

        # Layer 3: Embedding similarity
        result3 = await self.layer3.check(content)
        layer_results["embedding_similarity"] = result3
        if not result3.is_safe:
            logger.info("Layer 3 blocked content: %s", result3.reason)
            record_safety_block("embedding_similarity", result3.reason or "blocked")
            return ModerationResult(
                is_safe=False,
                risk_score=result3.risk_score,
                risk_level=result3.risk_level,
                blocked_by_layer=3,
                replacement_text=self.block_message,
                reason=result3.reason or "Blocked by embedding similarity layer",
                layer_results=layer_results,
            )

        # Combine risk from layers 1-3
        cumulative_score = self._combine_risk_scores([result1, result2, result3])

        # Layer 4: LLM judge (conditional)
        if self.layer4.should_run(cumulative_score):
            result4 = await self.layer4.check(content, context=context)
            layer_results["llm_judge"] = result4
            if not result4.is_safe:
                logger.info("Layer 4 blocked content: %s", result4.reason)
                record_safety_block("llm_judge", result4.reason or "blocked")
                return ModerationResult(
                    is_safe=False,
                    risk_score=result4.risk_score,
                    risk_level=result4.risk_level,
                    blocked_by_layer=4,
                    replacement_text=self.block_message,
                    reason=result4.reason or "Blocked by LLM judge layer",
                    layer_results=layer_results,
                )
            cumulative_score = max(cumulative_score, result4.risk_score)

        return ModerationResult(
            is_safe=True,
            risk_score=cumulative_score,
            risk_level=calculate_risk_level(cumulative_score),
            reason="Passed all moderation layers",
            layer_results=layer_results,
        )
