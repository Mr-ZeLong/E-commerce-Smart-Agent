"""意图识别服务层

整合所有组件，对外提供统一接口，会话状态管理（Redis）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.intent.classifier import IntentClassifier
from app.intent.clarification import ClarificationEngine, ClarificationResponse
from app.intent.models import ClarificationState, IntentCategory, IntentAction, IntentResult
from app.intent.multi_intent import MultiIntentProcessor
from app.intent.safety import SafetyFilter, SafetyCheckResult
from app.intent.slot_validator import SlotValidator
from app.intent.topic_switch import TopicSwitchDetector

logger = logging.getLogger(__name__)


class IntentRecognitionService:
    """意图识别服务

    整合所有意图识别组件，对外提供统一的意图识别接口。
    包含安全过滤、多意图处理、槽位验证、话题切换检测、
    澄清机制等功能，支持Redis缓存和会话状态管理。

    Attributes:
        llm: LLM模型实例，用于分类和澄清
        redis: Redis客户端，用于缓存和会话状态存储
        result_cache_ttl: 识别结果缓存TTL（秒），默认300秒
        session_cache_ttl: 会话状态缓存TTL（秒），默认1800秒
        classifier: 意图分类器
        slot_validator: 槽位验证器
        clarification_engine: 澄清引擎
        topic_switch_detector: 话题切换检测器
        multi_intent_processor: 多意图处理器
        safety_filter: 安全过滤器
    """

    def __init__(
        self,
        llm: Any | None = None,
        redis_client: Any | None = None,
        result_cache_ttl: int = 300,  # 识别结果缓存5分钟
        session_cache_ttl: int = 1800,  # 会话状态缓存30分钟
    ):
        self.llm = llm
        self.redis = redis_client
        self.result_cache_ttl = result_cache_ttl
        self.session_cache_ttl = session_cache_ttl

        # 初始化组件
        self.classifier = IntentClassifier(llm=llm)
        self.slot_validator = SlotValidator()
        self.clarification_engine = ClarificationEngine()
        self.topic_switch_detector = TopicSwitchDetector()
        self.multi_intent_processor = MultiIntentProcessor(classifier=self.classifier)
        self.safety_filter = SafetyFilter(llm=llm)

    async def recognize(
        self,
        query: str,
        session_id: str,
        conversation_history: list | None = None,
    ) -> IntentResult:
        """
        识别用户意图（主入口）

        Args:
            query: 用户输入
            session_id: 会话ID
            conversation_history: 对话历史

        Returns:
            IntentResult: 意图识别结果
        """
        # 1. 安全过滤
        safety_result = await self.safety_filter.check(query)
        if not safety_result.is_safe:
            # 返回安全警告意图
            return self._create_safety_warning_result(query, safety_result)

        # 2. 检查缓存（缓存中已包含安全检查结果，安全的内容才会被缓存）
        cached_result = await self._get_cached_result(query)
        if cached_result:
            return cached_result

        # 3. 加载会话状态
        state = await self._load_session_state(session_id)

        # 4. 多意图处理
        multi_result = await self.multi_intent_processor.process(
            query, conversation_history
        )

        if multi_result.is_multi_intent and len(multi_result.sub_intents) > 0:
            result = multi_result.sub_intents[0]
            # 合并共享槽位和特定槽位，特定槽位优先
            merged_slots = {**multi_result.shared_slots, **(result.slots or {})}
            result.slots = merged_slots
        else:
            # 5. 单意图分类
            result = await self.classifier.classify(query, conversation_history)

        # 6. 话题切换检测
        previous_result = state.current_intent if state else None
        switch_result = await self.topic_switch_detector.detect(
            result, previous_result, query, conversation_history
        )

        if switch_result.is_switch and switch_result.should_reset_context:
            # 重置会话状态
            state = ClarificationState(session_id=session_id)

        # 7. 槽位验证
        validation = self.slot_validator.validate(result)

        if not validation.is_complete:
            result.needs_clarification = True
            result.missing_slots = validation.missing_p0_slots

        # 8. 保存会话状态
        if state:
            state.current_intent = result
            await self._save_session_state(state)

        # 9. 缓存结果
        await self._cache_result(query, result)

        return result

    async def clarify(
        self,
        session_id: str,
        user_response: str,
    ) -> ClarificationResponse:
        """
        处理澄清回复

        Args:
            session_id: 会话ID
            user_response: 用户回复

        Returns:
            ClarificationResponse: 澄清响应
        """
        # 1. 加载会话状态
        state = await self._load_session_state(session_id)

        if not state or not state.current_intent:
            return ClarificationResponse(
                response="会话已过期，请重新描述您的问题。",
                state=ClarificationState(session_id=session_id),
                is_complete=True,
            )

        # 2. 安全过滤
        safety_result = await self.safety_filter.check(user_response)
        if not safety_result.is_safe:
            return ClarificationResponse(
                response="输入包含不安全内容，请重新输入。",
                state=state,
                is_complete=False,
            )

        # 3. 处理用户回复
        validation = self.slot_validator.validate(state.current_intent)
        response = await self.clarification_engine.handle_user_response(
            state, user_response, validation
        )

        # 4. 保存更新后的状态
        await self._save_session_state(response.state)

        return response

    async def _load_session_state(self, session_id: str) -> ClarificationState | None:
        """从Redis加载会话状态

        Args:
            session_id: 会话ID

        Returns:
            ClarificationState | None: 会话状态对象，未找到则返回None
        """
        if not self.redis:
            return None

        try:
            key = f"intent:session:{session_id}"
            data = await self.redis.get(key)
            if data:
                state_dict = json.loads(data)
                return self._deserialize_state(state_dict)
        except Exception as e:
            logger.warning(f"Failed to load session state: {e}")

        return None

    async def _save_session_state(self, state: ClarificationState) -> None:
        """保存会话状态到Redis

        Args:
            state: 会话状态对象
        """
        if not self.redis:
            return

        try:
            key = f"intent:session:{state.session_id}"
            state_dict = self._serialize_state(state)
            await self.redis.setex(key, self.session_cache_ttl, json.dumps(state_dict))
        except Exception as e:
            logger.warning(f"Failed to save session state: {e}")

    async def _get_cached_result(self, query: str) -> IntentResult | None:
        """获取缓存的识别结果

        Args:
            query: 用户查询字符串

        Returns:
            IntentResult | None: 缓存的识别结果，未命中则返回None
        """
        if not self.redis:
            return None

        try:
            query_hash = hashlib.sha256(query.encode()).hexdigest()
            key = f"intent:cache:{query_hash}"
            data = await self.redis.get(key)
            if data:
                result_dict = json.loads(data)
                return self._deserialize_result(result_dict)
        except Exception as e:
            logger.warning(f"Failed to get cached result: {e}")

        return None

    async def _cache_result(self, query: str, result: IntentResult) -> None:
        """缓存识别结果

        Args:
            query: 用户查询字符串
            result: 意图识别结果
        """
        if not self.redis:
            return

        try:
            query_hash = hashlib.sha256(query.encode()).hexdigest()
            key = f"intent:cache:{query_hash}"
            result_dict = result.to_dict()
            await self.redis.setex(key, self.result_cache_ttl, json.dumps(result_dict))
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    def _create_safety_warning_result(
        self, query: str, safety_result: SafetyCheckResult
    ) -> IntentResult:
        """创建安全警告结果

        Args:
            query: 原始用户查询
            safety_result: 安全检查结果

        Returns:
            IntentResult: 安全警告意图结果
        """
        return IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.CONSULT,
            confidence=0.0,
            needs_clarification=True,
            clarification_question=f"输入包含不安全内容（{safety_result.reason}），请重新输入。",
            raw_query=query,
        )

    def _serialize_state(self, state: ClarificationState) -> dict:
        """序列化会话状态

        Args:
            state: 会话状态对象

        Returns:
            dict: 序列化后的字典
        """
        return {
            "session_id": state.session_id,
            "current_intent": state.current_intent.to_dict() if state.current_intent else None,
            "clarification_round": state.clarification_round,
            "max_clarification_rounds": state.max_clarification_rounds,
            "asked_slots": state.asked_slots,
            "collected_slots": state.collected_slots,
            "pending_slot": state.pending_slot,
            "user_refused_slots": state.user_refused_slots,
            "clarification_history": state.clarification_history,
            "created_at": state.created_at.isoformat() if state.created_at else None,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    def _deserialize_state(self, data: dict) -> ClarificationState:
        """反序列化会话状态

        Args:
            data: 序列化的状态字典

        Returns:
            ClarificationState: 反序列化后的会话状态对象
        """
        from datetime import datetime

        state = ClarificationState(
            session_id=data["session_id"],
            clarification_round=data.get("clarification_round", 0),
            max_clarification_rounds=data.get("max_clarification_rounds", 3),
            asked_slots=data.get("asked_slots", []),
            collected_slots=data.get("collected_slots", {}),
            pending_slot=data.get("pending_slot"),
            user_refused_slots=data.get("user_refused_slots", []),
            clarification_history=data.get("clarification_history", []),
        )

        # 恢复datetime
        if data.get("created_at"):
            state.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            state.updated_at = datetime.fromisoformat(data["updated_at"])

        if data.get("current_intent"):
            intent_data = data["current_intent"]
            state.current_intent = IntentResult(
                primary_intent=IntentCategory(intent_data["primary_intent"]),
                secondary_intent=IntentAction(intent_data["secondary_intent"]),
                tertiary_intent=intent_data.get("tertiary_intent"),
                confidence=intent_data.get("confidence", 0.0),
                slots=intent_data.get("slots", {}),
                missing_slots=intent_data.get("missing_slots", []),
                needs_clarification=intent_data.get("needs_clarification", False),
                clarification_question=intent_data.get("clarification_question"),
                raw_query=intent_data.get("raw_query", ""),
            )

        return state

    def _deserialize_result(self, data: dict) -> IntentResult:
        """反序列化识别结果

        Args:
            data: 序列化的结果字典

        Returns:
            IntentResult: 反序列化后的意图识别结果
        """
        return IntentResult(
            primary_intent=IntentCategory(data["primary_intent"]),
            secondary_intent=IntentAction(data["secondary_intent"]),
            tertiary_intent=data.get("tertiary_intent"),
            confidence=data.get("confidence", 0.0),
            slots=data.get("slots", {}),
            missing_slots=data.get("missing_slots", []),
            needs_clarification=data.get("needs_clarification", False),
            clarification_question=data.get("clarification_question"),
            raw_query=data.get("raw_query", ""),
        )
