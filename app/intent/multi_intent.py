"""多意图处理器（简化版）

最多支持2个意图拆分，使用简单分隔符检测，槽位共享机制。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.intent.models import IntentResult


@dataclass
class MultiIntentResult:
    """多意图处理结果"""
    is_multi_intent: bool
    sub_intents: list[IntentResult] = field(default_factory=list)
    shared_slots: dict[str, Any] = field(default_factory=dict)
    execution_order: list[int] = field(default_factory=list)


class MultiIntentProcessor:
    """多意图处理器（简化版）"""

    # 意图分隔符
    INTENT_SEPARATORS = [
        "顺便", "还有", "另外", "以及", "和",
        "，然后", "。另外", "。还有",
        ";", "；",
    ]

    # 最多支持的意图数量
    MAX_INTENTS = 2

    def __init__(self, classifier: Any | None = None):
        self.classifier = classifier

    async def process(
        self, query: str, conversation_history: list | None = None
    ) -> MultiIntentResult:
        """
        处理多意图

        Args:
            query: 用户输入
            conversation_history: 对话历史

        Returns:
            MultiIntentResult: 多意图处理结果
        """
        # 1. 检测是否多意图
        segments = self._split_query(query)

        if len(segments) == 1:
            # 单意图
            if self.classifier:
                result = await self.classifier.classify(query, conversation_history)
                return MultiIntentResult(
                    is_multi_intent=False,
                    sub_intents=[result],
                    shared_slots=result.slots if result else {},
                    execution_order=[0],
                )
            return MultiIntentResult(is_multi_intent=False)

        # 2. 限制最多2个意图
        segments = segments[: self.MAX_INTENTS]

        # 3. 分别识别每个意图
        sub_intents: list[IntentResult] = []
        for segment in segments:
            if self.classifier:
                result = await self.classifier.classify(segment.strip(), conversation_history)
                if result:
                    sub_intents.append(result)

        # 4. 提取共享槽位
        shared_slots = self._extract_shared_slots(sub_intents)

        # 5. 确定执行顺序
        execution_order = self._determine_execution_order(sub_intents)

        return MultiIntentResult(
            is_multi_intent=True,
            sub_intents=sub_intents,
            shared_slots=shared_slots,
            execution_order=execution_order,
        )

    def _split_query(self, query: str) -> list[str]:
        """使用分隔符拆分查询"""
        segments = [query]

        # 按长度降序排序，确保长分隔符优先匹配（如"。另外"先于"另外"）
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
        """提取共享槽位"""
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
        """确定意图执行顺序（按优先级）"""
        # 简化版：按原始顺序执行
        # 实际可根据意图类型调整（如QUERY优先于APPLY）
        return list(range(len(sub_intents)))

    def apply_shared_slots(
        self, sub_intents: list[IntentResult], shared_slots: dict[str, Any]
    ) -> list[IntentResult]:
        """将共享槽位应用到所有子意图"""
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
