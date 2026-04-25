"""多意图处理器（简化版）"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from app.core.tracing import build_llm_config
from app.intent.models import IntentResult


class _Classifier(Protocol):
    async def classify(self, query: str, context: dict[str, Any] | None = None) -> IntentResult: ...


logger = logging.getLogger(__name__)


class IndependenceCheck(BaseModel):
    are_independent: bool = Field(description="两个意图是否可以独立并行处理")
    reason: str = Field(description="判断理由")


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

    def __init__(
        self, classifier: _Classifier, mode: str = "cascade", llm: BaseChatModel | None = None
    ):
        self.classifier = classifier
        self.mode = mode
        self.llm = llm

    async def process(
        self,
        query: str,
        conversation_history: list | None = None,
        db_session=None,
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
        rule_based: bool | None = None
        llm_check: IndependenceCheck | None = None
        if len(sub_intents) == 2:
            rule_based = are_independent(
                sub_intents[0].primary_intent.value, sub_intents[1].primary_intent.value
            )
            if rule_based:
                independent = True
            elif self.llm is not None:
                llm_check = await self._llm_independence_check(query, sub_intents)
                independent = llm_check.are_independent

        if db_session is not None and llm_check is not None:
            await self._log_decision(
                db_session,
                query,
                sub_intents[0].primary_intent.value,
                sub_intents[1].primary_intent.value,
                rule_based,
                llm_check,
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

    async def _log_decision(
        self,
        db_session,
        query: str,
        intent_a: str,
        intent_b: str,
        rule_based: bool | None,
        llm_check: IndependenceCheck,
    ) -> None:
        from app.models.multi_intent_log import MultiIntentDecisionLog

        log = MultiIntentDecisionLog(
            query=query,
            intent_a=intent_a,
            intent_b=intent_b,
            rule_based_result=rule_based,
            llm_result=llm_check.are_independent,
            llm_reason=llm_check.reason,
        )
        db_session.add(log)
        await db_session.commit()

    async def _llm_independence_check(
        self, query: str, sub_intents: list[IntentResult]
    ) -> IndependenceCheck:
        from langchain_core.prompts import ChatPromptTemplate

        intent_a = sub_intents[0].primary_intent.value
        intent_b = sub_intents[1].primary_intent.value
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位意图分析专家。判断以下两个用户意图是否可以独立并行处理，互不干扰。",
                ),
                (
                    "human",
                    f"用户原始问题: {query}\n"
                    f"意图A: {intent_a}\n"
                    f"意图B: {intent_b}\n"
                    "这两个意图是否可以由两个不同的客服专员同时处理？",
                ),
            ]
        )
        try:
            if self.llm is None:
                raise RuntimeError("LLM not available")
            checker = prompt | self.llm.with_structured_output(IndependenceCheck)
            config = build_llm_config(
                agent_name="multi_intent_checker",
                tags=["intent", "internal"],
            )
            result = await checker.ainvoke({}, config=config)
            if isinstance(result, IndependenceCheck):
                return result
            if isinstance(result, dict):
                return IndependenceCheck(**result)
            return IndependenceCheck(are_independent=False, reason="Unexpected output type")
        except (LangChainException, ConnectionError, OSError, Exception) as exc:
            logger.warning("LLM independence check failed: %s", exc)
            return IndependenceCheck(are_independent=False, reason="LLM check failed")

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
