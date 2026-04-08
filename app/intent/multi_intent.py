"""多意图处理器（简化版）

最多支持2个意图拆分，使用简单分隔符检测，槽位共享机制。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from app.intent.models import IntentResult

logger = logging.getLogger(__name__)


class IntentClassifierProtocol(Protocol):
    """意图分类器协议"""

    async def classify(
        self, query: str, context: dict[str, Any] | None = None
    ) -> IntentResult | None:
        """分类用户意图

        Args:
            query: 用户输入
            context: 可选的上下文信息

        Returns:
            IntentResult或None（如果分类失败）
        """
        ...


@dataclass
class MultiIntentResult:
    """多意图处理结果

    Attributes:
        is_multi_intent: 是否为多意图
        sub_intents: 子意图列表
        shared_slots: 共享槽位
        execution_order: 执行顺序索引列表
    """

    is_multi_intent: bool
    sub_intents: list[IntentResult] = field(default_factory=list)
    shared_slots: dict[str, Any] = field(default_factory=dict)
    execution_order: list[int] = field(default_factory=list)


class MultiIntentProcessor:
    """多意图处理器（简化版）

    支持单意图和多意图两种处理模式：
    - single模式：只返回置信度最高的意图
    - cascade模式：返回所有识别到的意图（默认）

    Attributes:
        INTENT_SEPARATORS: 意图分隔符列表
        MAX_INTENTS: 最多支持的意图数量
    """

    # 意图分隔符
    INTENT_SEPARATORS: ClassVar[list[str]] = [
        "顺便",
        "还有",
        "另外",
        "以及",
        "和",
        "，然后",
        "。另外",
        "。还有",
        ";",
        "；",
    ]

    # 最多支持的意图数量
    MAX_INTENTS: ClassVar[int] = 2

    # 支持的模式
    VALID_MODES: ClassVar[set[str]] = {"single", "cascade"}

    def __init__(
        self,
        classifier: IntentClassifierProtocol | None = None,
        mode: str = "cascade",
    ):
        """初始化多意图处理器

        Args:
            classifier: 意图分类器实例
            mode: 处理模式，"single"或"cascade"

        Raises:
            ValueError: 如果mode参数无效
        """
        if mode not in self.VALID_MODES:
            raise ValueError(
                f"Invalid mode: {mode}. Must be one of {self.VALID_MODES}"
            )

        self.classifier = classifier
        self.mode = mode
        logger.debug(
            "MultiIntentProcessor initialized with mode=%s, classifier=%s",
            mode,
            "present" if classifier else "none",
        )

    async def process(
        self, query: str, conversation_history: list | None = None
    ) -> MultiIntentResult:
        """处理多意图

        根据配置的模式处理用户输入：
        - single模式：只返回置信度最高的意图
        - cascade模式：返回所有识别到的意图

        Args:
            query: 用户输入
            conversation_history: 对话历史

        Returns:
            MultiIntentResult: 多意图处理结果

        Raises:
            Exception: 分类器调用失败且无法恢复时
        """
        logger.info("Processing query: %s", query)

        # 1. 检测是否多意图
        segments = self._split_query(query)
        logger.debug("Query split into %d segments: %s", len(segments), segments)

        if len(segments) == 1:
            # 单意图
            logger.debug("Single intent detected")
            if self.classifier:
                try:
                    result = await self.classifier.classify(
                        query, conversation_history
                    )
                    logger.debug("Classifier returned result: %s", result)
                    return MultiIntentResult(
                        is_multi_intent=False,
                        sub_intents=[result] if result else [],
                        shared_slots=result.slots if result else {},
                        execution_order=[0] if result else [],
                    )
                except Exception as e:
                    logger.error("Classifier failed for single intent: %s", e)
                    # 优雅降级：返回空结果
                    return MultiIntentResult(is_multi_intent=False)
            return MultiIntentResult(is_multi_intent=False)

        # 2. 限制最多2个意图
        segments = segments[: self.MAX_INTENTS]
        logger.info(
            "Multi-intent detected with %d segments (max %d)",
            len(segments),
            self.MAX_INTENTS,
        )

        # 3. 分别识别每个意图
        sub_intents: list[IntentResult] = []
        for i, segment in enumerate(segments):
            if self.classifier:
                try:
                    logger.debug(
                        "Classifying segment %d/%d: %s", i + 1, len(segments), segment
                    )
                    result = await self.classifier.classify(
                        segment.strip(), conversation_history
                    )
                    if result:
                        sub_intents.append(result)
                        logger.debug(
                            "Segment %d classified as: %s (confidence=%.2f)",
                            i + 1,
                            result.primary_intent.value,
                            result.confidence,
                        )
                except Exception as e:
                    logger.error("Classifier failed for segment '%s': %s", segment, e)
                    # 继续处理其他segment，优雅降级
                    continue

        # 4. 提取共享槽位
        shared_slots = self._extract_shared_slots(sub_intents)
        logger.debug("Extracted shared slots: %s", shared_slots)

        # 5. 确定执行顺序（按置信度降序）
        execution_order = self._determine_execution_order(sub_intents)
        logger.debug("Execution order: %s", execution_order)

        # 6. 根据模式处理结果
        if self.mode == "single" and sub_intents:
            # single模式：只保留置信度最高的意图
            if execution_order:
                highest_confidence_idx = execution_order[0]
                filtered_sub_intents = [sub_intents[highest_confidence_idx]]
                filtered_execution_order = [0]
                logger.info(
                    "Single mode: selected intent with highest confidence (index=%d)",
                    highest_confidence_idx,
                )
            else:
                filtered_sub_intents = []
                filtered_execution_order = []

            return MultiIntentResult(
                is_multi_intent=len(segments) > 1,
                sub_intents=filtered_sub_intents,
                shared_slots=shared_slots,
                execution_order=filtered_execution_order,
            )

        # cascade模式：返回所有意图（默认行为）
        return MultiIntentResult(
            is_multi_intent=True,
            sub_intents=sub_intents,
            shared_slots=shared_slots,
            execution_order=execution_order,
        )

    def _split_query(self, query: str) -> list[str]:
        """使用分隔符拆分查询

        按长度降序排序分隔符，确保长分隔符优先匹配
        （如"。另外"先于"另外"）

        Args:
            query: 用户输入

        Returns:
            拆分后的查询片段列表
        """
        segments = [query]

        # 按长度降序排序，确保长分隔符优先匹配
        sorted_separators = sorted(self.INTENT_SEPARATORS, key=len, reverse=True)

        for separator in sorted_separators:
            new_segments = []
            for segment in segments:
                if separator in segment:
                    new_segments.extend(segment.split(separator))
                else:
                    new_segments.append(segment)
            segments = [s.strip() for s in new_segments if s.strip()]

        return segments

    def _extract_shared_slots(self, sub_intents: list[IntentResult]) -> dict[str, Any]:
        """提取共享槽位

        从第一个意图获取所有槽位作为候选，后续意图的新槽位合并进来。
        第一个意图的槽位值具有优先权。

        Args:
            sub_intents: 子意图列表

        Returns:
            共享槽位字典
        """
        if not sub_intents:
            return {}

        # 从第一个意图获取所有槽位作为候选
        shared = dict(sub_intents[0].slots) if sub_intents[0].slots else {}

        # 后续意图的槽位也合并进来
        for intent in sub_intents[1:]:
            if intent.slots:
                for key, value in intent.slots.items():
                    if key not in shared:
                        shared[key] = value

        return shared

    def _determine_execution_order(self, sub_intents: list[IntentResult]) -> list[int]:
        """确定意图执行顺序

        按置信度降序排序，置信度高的优先执行。
        返回的是原始索引列表。

        Args:
            sub_intents: 子意图列表

        Returns:
            按执行顺序排列的索引列表
        """
        if not sub_intents:
            return []

        # 按置信度降序排序，返回原始索引
        indexed_intents = list(enumerate(sub_intents))
        sorted_by_confidence = sorted(
            indexed_intents,
            key=lambda x: x[1].confidence if x[1].confidence else 0.0,
            reverse=True,
        )
        return [idx for idx, _ in sorted_by_confidence]

    def apply_shared_slots(
        self, sub_intents: list[IntentResult], shared_slots: dict[str, Any]
    ) -> list[IntentResult]:
        """将共享槽位应用到所有子意图

        合并共享槽位和意图自身的槽位，意图自身的槽位优先。

        Args:
            sub_intents: 子意图列表
            shared_slots: 共享槽位字典

        Returns:
            更新后的子意图列表
        """
        updated = []
        for intent in sub_intents:
            if intent.slots:
                merged_slots = {**shared_slots, **intent.slots}
            else:
                merged_slots = dict(shared_slots)

            # 创建新的IntentResult
            updated_intent = IntentResult(
                primary_intent=intent.primary_intent,
                secondary_intent=intent.secondary_intent,
                tertiary_intent=intent.tertiary_intent,
                confidence=intent.confidence,
                slots=merged_slots,
                missing_slots=intent.missing_slots,
                needs_clarification=intent.needs_clarification,
                clarification_question=intent.clarification_question,
                raw_query=intent.raw_query,
            )
            updated.append(updated_intent)

        return updated
