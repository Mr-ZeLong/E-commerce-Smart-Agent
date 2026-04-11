import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.confidence.signals import calculate_confidence_signals
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfidenceEvaluator:
    """负责置信度评估"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

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
        try:
            signals = await calculate_confidence_signals(temp_state, answer, self.llm)
        except RuntimeError as exc:
            logger.warning(f"Confidence evaluation failed, falling back to manual audit: {exc}")
            return {
                "confidence_score": 0.0,
                "confidence_signals": {},
                "needs_human_transfer": True,
                "transfer_reason": f"confidence_evaluation_failed: {exc}",
                "audit_level": "manual",
            }

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
                "rag": signals["rag"].model_dump(),
                "llm": signals["llm"].model_dump(),
                "emotion": signals["emotion"].model_dump(),
            },
            "needs_human_transfer": needs_transfer,
            "transfer_reason": "置信度不足" if needs_transfer else None,
            "audit_level": audit_level,
        }
