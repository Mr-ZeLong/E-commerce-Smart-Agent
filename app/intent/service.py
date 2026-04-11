"""意图识别服务层"""

from __future__ import annotations

import hashlib
import json
import logging

import redis.asyncio as aioredis
from langchain_openai import ChatOpenAI

from app.intent.clarification import ClarificationEngine, ClarificationResponse
from app.intent.classifier import IntentClassifier
from app.intent.models import ClarificationState, IntentAction, IntentCategory, IntentResult
from app.intent.multi_intent import MultiIntentProcessor
from app.intent.safety import SafetyCheckResult, SafetyConfig, SafetyFilter
from app.intent.slot_validator import SlotValidator
from app.intent.topic_switch import TopicSwitchDetector

logger = logging.getLogger(__name__)


class IntentRecognitionService:
    def __init__(
        self,
        llm: ChatOpenAI,
        redis_client: aioredis.Redis,
        result_cache_ttl: int = 300,
        session_cache_ttl: int = 1800,
    ):
        self.llm = llm
        self.redis = redis_client
        self.result_cache_ttl = result_cache_ttl
        self.session_cache_ttl = session_cache_ttl
        self.classifier = IntentClassifier(llm=llm)
        self.slot_validator = SlotValidator()
        self.clarification_engine = ClarificationEngine(slot_validator=self.slot_validator)
        self.topic_switch_detector = TopicSwitchDetector()
        self.multi_intent_processor = MultiIntentProcessor(classifier=self.classifier)
        self.safety_filter = SafetyFilter(llm=llm, config=SafetyConfig())

    async def recognize(
        self,
        query: str,
        session_id: str,
        conversation_history: list | None = None,
    ) -> IntentResult:
        safety_result = await self.safety_filter.check(query)
        if not safety_result.is_safe:
            return self._create_safety_warning_result(query, safety_result)

        cached_result = await self._get_cached_result(query)
        if cached_result:
            return cached_result

        state = await self._load_session_state(session_id)

        multi_result = await self.multi_intent_processor.process(query, conversation_history)
        if multi_result.is_multi_intent and multi_result.sub_intents:
            result = multi_result.sub_intents[0]
            merged_slots = {**multi_result.shared_slots, **(result.slots or {})}
            result.slots = merged_slots
            if len(multi_result.sub_intents) > 1:
                result.slots["pending_intents"] = [
                    {
                        "primary_intent": si.primary_intent.value,
                        "secondary_intent": si.secondary_intent.value,
                        "slots": si.slots,
                    }
                    for si in multi_result.sub_intents[1:]
                ]
        else:
            context = {"history": conversation_history} if conversation_history else None
            result = await self.classifier.classify(query, context)

        previous_result = state.current_intent if state else None
        switch_result = self.topic_switch_detector.detect(result, previous_result, query)
        if switch_result.is_switch and switch_result.should_reset_context:
            state = ClarificationState(session_id=session_id)

        validation = self.slot_validator.validate(result)
        if not validation.is_complete:
            result.needs_clarification = True
            result.missing_slots = validation.missing_p0_slots

        if state:
            state.current_intent = result
            await self._save_session_state(state)

        await self._cache_result(query, result)
        return result

    async def clarify(self, session_id: str, user_response: str) -> ClarificationResponse:
        state = await self._load_session_state(session_id)
        if not state or not state.current_intent:
            return ClarificationResponse(
                response="会话已过期，请重新描述您的问题。",
                state=ClarificationState(session_id=session_id),
                is_complete=True,
            )

        safety_result = await self.safety_filter.check(user_response)
        if not safety_result.is_safe:
            return ClarificationResponse(
                response="输入包含不安全内容，请重新输入。",
                state=state,
                is_complete=False,
            )

        validation = self.slot_validator.validate(state.current_intent)
        response = await self.clarification_engine.handle_user_response(
            state, user_response, validation
        )

        if response.state.current_intent and response.state.collected_slots:
            if response.state.current_intent.slots is None:
                response.state.current_intent.slots = {}
            response.state.current_intent.slots.update(response.state.collected_slots)

        await self._save_session_state(response.state)
        return response

    async def _load_session_state(self, session_id: str) -> ClarificationState | None:
        try:
            key = f"intent:session:{session_id}"
            data = await self.redis.get(key)
            if data:
                return ClarificationState.model_validate_json(data)
        except (aioredis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load session state: {e}")
        return None

    async def _save_session_state(self, state: ClarificationState) -> None:
        try:
            key = f"intent:session:{state.session_id}"
            await self.redis.setex(key, self.session_cache_ttl, state.model_dump_json())
        except aioredis.RedisError as e:
            logger.warning(f"Failed to save session state: {e}")

    async def _get_cached_result(self, query: str) -> IntentResult | None:
        try:
            query_hash = hashlib.sha256(query.encode()).hexdigest()
            key = f"intent:cache:{query_hash}"
            data = await self.redis.get(key)
            if data:
                return IntentResult.model_validate_json(data)
        except (aioredis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to get cached result: {e}")
        return None

    async def _cache_result(self, query: str, result: IntentResult) -> None:
        try:
            query_hash = hashlib.sha256(query.encode()).hexdigest()
            key = f"intent:cache:{query_hash}"
            await self.redis.setex(key, self.result_cache_ttl, result.model_dump_json())
        except aioredis.RedisError as e:
            logger.warning(f"Failed to cache result: {e}")

    def _create_safety_warning_result(
        self, query: str, safety_result: SafetyCheckResult
    ) -> IntentResult:
        return IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.CONSULT,
            confidence=0.0,
            needs_clarification=True,
            clarification_question=f"输入包含不安全内容（{safety_result.reason}），请重新输入。",
            raw_query=query,
        )
