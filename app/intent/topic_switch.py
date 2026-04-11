from __future__ import annotations

from pydantic import BaseModel

from app.intent.config import check_intent_compatibility
from app.intent.models import IntentResult


class TopicSwitchResult(BaseModel):
    is_switch: bool
    switch_type: str | None
    confidence: float
    reason: str
    should_reset_context: bool = False


class TopicSwitchDetector:
    EXPLICIT_SWITCH_KEYWORDS = [
        "换个话题",
        "另外",
        "还有",
        "对了",
        "顺便问",
        "不说这个",
        "问别的",
        "还有一个问题",
        "by the way",
        "另外问一下",
        "再问一个",
    ]
    CONFIDENCE_DROP_THRESHOLD = 0.3
    CONFIDENCE_THRESHOLD = 0.5

    def detect(
        self,
        current_result: IntentResult,
        previous_result: IntentResult | None,
        query: str,
    ) -> TopicSwitchResult:
        query_lower = query.lower()
        for keyword in self.EXPLICIT_SWITCH_KEYWORDS:
            if keyword in query_lower:
                return TopicSwitchResult(
                    is_switch=True,
                    switch_type="explicit",
                    confidence=0.9,
                    reason=f"显式切换: {keyword}",
                    should_reset_context=True,
                )

        if not previous_result:
            return TopicSwitchResult(
                is_switch=False,
                switch_type=None,
                confidence=current_result.confidence,
                reason="无历史意图",
            )

        confidence_drop = previous_result.confidence - current_result.confidence
        if confidence_drop > self.CONFIDENCE_DROP_THRESHOLD:
            return TopicSwitchResult(
                is_switch=True,
                switch_type="implicit",
                confidence=current_result.confidence,
                reason=f"置信度下降: {previous_result.confidence:.2f} -> {current_result.confidence:.2f}",
            )

        current_intent = (
            f"{current_result.primary_intent.value}/{current_result.secondary_intent.value}"
        )
        previous_intent = (
            f"{previous_result.primary_intent.value}/{previous_result.secondary_intent.value}"
        )

        if (
            current_intent != previous_intent
            and current_result.confidence < self.CONFIDENCE_THRESHOLD
        ):
            return TopicSwitchResult(
                is_switch=True,
                switch_type="implicit",
                confidence=current_result.confidence,
                reason=f"意图变化且置信度低: {previous_intent} -> {current_intent}",
            )

        if not check_intent_compatibility(previous_intent, current_intent):
            return TopicSwitchResult(
                is_switch=True,
                switch_type="implicit",
                confidence=current_result.confidence,
                reason=f"意图不兼容: {previous_intent} -> {current_intent}",
                should_reset_context=True,
            )

        return TopicSwitchResult(
            is_switch=False,
            switch_type="compatible",
            confidence=current_result.confidence,
            reason=f"意图兼容: {previous_intent} -> {current_intent}",
        )
