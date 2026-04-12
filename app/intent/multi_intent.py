"""多意图处理器（简化版）"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.intent.classifier import IntentClassifier
from app.intent.models import IntentResult

logger = logging.getLogger(__name__)


class MultiIntentResult(BaseModel):
    is_multi_intent: bool
    sub_intents: list[IntentResult] = Field(default_factory=list)
    shared_slots: dict[str, Any] = Field(default_factory=dict)
    execution_order: list[int] = Field(default_factory=list)
    are_independent: bool = False


_INDEPENDENT_INTENT_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("ORDER", "POLICY"),
        ("POLICY", "ORDER"),
        ("LOGISTICS", "POLICY"),
        ("POLICY", "LOGISTICS"),
        ("ACCOUNT", "POLICY"),
        ("POLICY", "ACCOUNT"),
        ("PRODUCT", "POLICY"),
        ("POLICY", "PRODUCT"),
        ("ORDER", "PRODUCT"),
        ("PRODUCT", "ORDER"),
        ("LOGISTICS", "PRODUCT"),
        ("PRODUCT", "LOGISTICS"),
        ("ACCOUNT", "PRODUCT"),
        ("PRODUCT", "ACCOUNT"),
    }
)

_DEPENDENT_INTENT_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("CART", "PAYMENT"),
        ("PAYMENT", "CART"),
        ("ORDER", "REFUND"),
        ("REFUND", "ORDER"),
        ("CART", "ORDER"),
        ("ORDER", "CART"),
    }
)


def are_independent(intent_a: str, intent_b: str) -> bool:
    if intent_a == intent_b:
        return False
    pair = (intent_a, intent_b)
    if pair in _INDEPENDENT_INTENT_PAIRS:
        return True
    if pair in _DEPENDENT_INTENT_PAIRS:
        return False
    return False


class MultiIntentProcessor:
    SEPARATORS = ["顺便", "还有", "另外", "以及", "，然后", "。另外", "。还有", ";", "；"]
    MAX_INTENTS = 2

    def __init__(self, classifier: IntentClassifier, mode: str = "cascade"):
        self.classifier = classifier
        self.mode = mode

    async def process(
        self, query: str, conversation_history: list | None = None
    ) -> MultiIntentResult:
        context = {"history": conversation_history} if conversation_history else None
        segments = self._split_query(query)
        if len(segments) == 1:
            result = await self.classifier.classify(query, context)
            return MultiIntentResult(
                is_multi_intent=False,
                sub_intents=[result],
                shared_slots=result.slots or {},
                execution_order=[0],
            )

        segments = segments[: self.MAX_INTENTS]
        sub_intents: list[IntentResult] = []
        for segment in segments:
            result = await self.classifier.classify(segment.strip(), context)
            sub_intents.append(result)

        shared_slots = self._extract_shared_slots(sub_intents)
        execution_order = list(range(len(sub_intents)))
        independent = False
        if len(sub_intents) == 2:
            independent = are_independent(
                sub_intents[0].primary_intent.value, sub_intents[1].primary_intent.value
            )

        if self.mode == "single" and sub_intents:
            best = max(sub_intents, key=lambda r: r.confidence or 0.0)
            return MultiIntentResult(
                is_multi_intent=True,
                sub_intents=[best],
                shared_slots=shared_slots,
                execution_order=[0],
                are_independent=independent,
            )

        return MultiIntentResult(
            is_multi_intent=True,
            sub_intents=sub_intents,
            shared_slots=shared_slots,
            execution_order=execution_order,
            are_independent=independent,
        )

    def _split_query(self, query: str) -> list[str]:
        segments: list[str] = [query]
        sorted_separators = sorted(self.SEPARATORS, key=lambda s: len(s), reverse=True)
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
        if not sub_intents:
            return {}
        shared = dict(sub_intents[0].slots or {})
        for intent in sub_intents[1:]:
            if intent.slots:
                for key, value in intent.slots.items():
                    if key not in shared:
                        shared[key] = value
        return shared
