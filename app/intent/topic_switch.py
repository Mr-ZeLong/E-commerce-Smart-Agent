"""话题切换检测器

显式切换检测（关键词）、隐式切换检测（置信度下降）、意图兼容性检查。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.intent.config import check_intent_compatibility
from app.intent.models import IntentResult


@dataclass
class TopicSwitchResult:
    """话题切换检测结果"""
    is_switch: bool
    switch_type: str | None  # "explicit", "implicit", "compatible"
    confidence: float
    reason: str
    should_reset_context: bool = False


class TopicSwitchDetector:
    """话题切换检测器"""

    # 显式切换关键词
    EXPLICIT_SWITCH_KEYWORDS = [
        "换个话题", "另外", "还有", "对了", "顺便问",
        "不说这个", "问别的", "还有一个问题",
        "by the way", "另外问一下", "再问一个",
    ]

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.5
    CONFIDENCE_DROP_THRESHOLD = 0.3

    def __init__(self):
        self._last_intent: IntentResult | None = None
        self._last_confidence: float = 0.0

    async def detect(
        self,
        current_result: IntentResult,
        previous_result: IntentResult | None,
        query: str,
        conversation_history: list[dict] | None = None,
    ) -> TopicSwitchResult:
        """
        检测话题切换

        Args:
            current_result: 当前意图识别结果
            previous_result: 上一次意图识别结果
            query: 用户输入
            conversation_history: 对话历史

        Returns:
            TopicSwitchResult: 检测结果
        """
        # 1. 显式切换检测
        explicit_result = self._detect_explicit_switch(query)
        if explicit_result.is_switch:
            return explicit_result

        # 2. 隐式切换检测
        if previous_result:
            implicit_result = self._detect_implicit_switch(
                current_result, previous_result, query
            )
            if implicit_result.is_switch:
                return implicit_result

            # 3. 意图兼容性检查
            compatibility_result = self._check_compatibility(
                current_result, previous_result
            )
            # Return compatibility result (either compatible or incompatible)
            return compatibility_result

        # 无历史意图时的默认返回
        return TopicSwitchResult(
            is_switch=False,
            switch_type=None,
            confidence=current_result.confidence,
            reason="话题连续",
            should_reset_context=False,
        )

    def _detect_explicit_switch(self, query: str) -> TopicSwitchResult:
        """检测显式话题切换"""
        query_lower = query.lower()

        for keyword in self.EXPLICIT_SWITCH_KEYWORDS:
            if keyword in query_lower:
                return TopicSwitchResult(
                    is_switch=True,
                    switch_type="explicit",
                    confidence=0.9,
                    reason=f"检测到显式切换关键词: {keyword}",
                    should_reset_context=True,
                )

        return TopicSwitchResult(
            is_switch=False,
            switch_type=None,
            confidence=0.0,
            reason="无显式切换",
        )

    def _detect_implicit_switch(
        self,
        current: IntentResult,
        previous: IntentResult,
        query: str,
    ) -> TopicSwitchResult:
        """检测隐式话题切换"""
        # 1. 置信度下降检测
        confidence_drop = previous.confidence - current.confidence

        if confidence_drop > self.CONFIDENCE_DROP_THRESHOLD:
            return TopicSwitchResult(
                is_switch=True,
                switch_type="implicit",
                confidence=current.confidence,
                reason=f"置信度下降: {previous.confidence:.2f} -> {current.confidence:.2f}",
                should_reset_context=False,
            )

        # 2. 意图类别变化检测
        current_intent = f"{current.primary_intent.value}/{current.secondary_intent.value}"
        previous_intent = f"{previous.primary_intent.value}/{previous.secondary_intent.value}"

        if current_intent != previous_intent and current.confidence < self.CONFIDENCE_THRESHOLD:
            return TopicSwitchResult(
                is_switch=True,
                switch_type="implicit",
                confidence=current.confidence,
                reason=f"意图变化且置信度低: {previous_intent} -> {current_intent}",
                should_reset_context=False,
            )

        return TopicSwitchResult(
            is_switch=False,
            switch_type=None,
            confidence=current.confidence,
            reason="无隐式切换",
        )

    def _check_compatibility(
        self, current: IntentResult, previous: IntentResult
    ) -> TopicSwitchResult:
        """检查意图兼容性"""
        current_intent = f"{current.primary_intent.value}/{current.secondary_intent.value}"
        previous_intent = f"{previous.primary_intent.value}/{previous.secondary_intent.value}"

        is_compatible = check_intent_compatibility(previous_intent, current_intent)

        if is_compatible:
            return TopicSwitchResult(
                is_switch=False,  # 兼容不算切换
                switch_type="compatible",
                confidence=current.confidence,
                reason=f"意图兼容: {previous_intent} -> {current_intent}",
                should_reset_context=False,
            )

        return TopicSwitchResult(
            is_switch=True,
            switch_type="implicit",
            confidence=current.confidence,
            reason=f"意图不兼容: {previous_intent} -> {current_intent}",
            should_reset_context=True,
        )

    def update_state(self, result: IntentResult):
        """更新检测器状态"""
        self._last_intent = result
        self._last_confidence = result.confidence
