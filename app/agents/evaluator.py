import logging
from typing import Any

from app.confidence.signals import ConfidenceSignals
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfidenceEvaluator:
    """负责置信度评估"""

    async def evaluate(
        self, question: str, answer: str, history: list, retrieval_result: Any | None
    ) -> dict:
        """
        计算置信度并返回评估结果字典，包含：
        - confidence_score
        - confidence_signals
        - needs_human_transfer
        - transfer_reason
        - audit_level
        """
        # 构建临时状态用于信号计算（仅作为信号计算器的输入字典）
        temp_state: dict[str, Any] = {
            "question": question,
            "history": history,
            "retrieval_result": retrieval_result,
        }

        # 计算置信度信号
        confidence_signals = ConfidenceSignals(temp_state)
        signals = await confidence_signals.calculate_all(answer)

        # 计算加权总分
        weights = settings.CONFIDENCE.default_weights
        overall_score = (
            signals["rag"].score * weights["rag"]
            + signals["llm"].score * weights["llm"]
            + signals["emotion"].score * weights["emotion"]
        )

        # 确定审核级别
        audit_level = settings.CONFIDENCE.get_audit_level(overall_score)
        needs_transfer = audit_level == "manual"

        return {
            "confidence_score": overall_score,
            "confidence_signals": {
                "rag": {"score": signals["rag"].score, "reason": signals["rag"].reason},
                "llm": {"score": signals["llm"].score, "reason": signals["llm"].reason},
                "emotion": {"score": signals["emotion"].score, "reason": signals["emotion"].reason},
            },
            "needs_human_transfer": needs_transfer,
            "transfer_reason": "置信度不足" if needs_transfer else None,
            "audit_level": audit_level,
        }
