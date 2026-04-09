"""新的意图路由Agent

使用分层意图识别系统替换原有的规则+LLM混合方案。
"""

import logging
from enum import Enum
from typing import Any, TypedDict

from app.agents.base import AgentResult, BaseAgent
from app.intent import IntentRecognitionService
from app.intent.models import IntentCategory, IntentResult

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """意图枚举（向后兼容）"""
    ORDER = "ORDER"
    POLICY = "POLICY"
    REFUND = "REFUND"
    OTHER = "OTHER"


class _IntentMapping(TypedDict):
    legacy: Intent
    agent: str


class RouterState(TypedDict, total=False):
    """路由状态字典类型定义

    Attributes:
        question: 用户输入的问题
        thread_id: 会话ID
        user_id: 用户ID（字符串或整数）
        history: 对话历史记录
        intent_result: 意图识别结果字典
        slots: 提取的槽位信息
        awaiting_clarification: 是否等待澄清
        clarification_state: 澄清状态
        intent: 向后兼容的意图枚举
        next_agent: 下一个路由的Agent名称
    """
    question: str
    thread_id: str
    user_id: str | int
    history: list[dict[str, Any]]
    intent_result: dict[str, Any]
    slots: dict[str, Any]
    awaiting_clarification: bool
    clarification_state: dict[str, Any]
    intent: Intent
    next_agent: str


_INTENT_MAPPINGS: dict[IntentCategory, _IntentMapping] = {
    IntentCategory.ORDER: {"legacy": Intent.ORDER, "agent": "order"},
    IntentCategory.AFTER_SALES: {"legacy": Intent.REFUND, "agent": "order"},
    IntentCategory.POLICY: {"legacy": Intent.POLICY, "agent": "policy"},
    IntentCategory.PRODUCT: {"legacy": Intent.POLICY, "agent": "policy"},
    IntentCategory.RECOMMENDATION: {"legacy": Intent.POLICY, "agent": "policy"},
    IntentCategory.CART: {"legacy": Intent.ORDER, "agent": "order"},
    IntentCategory.OTHER: {"legacy": Intent.OTHER, "agent": "supervisor"},
}


class IntentRouterAgent(BaseAgent):
    """意图路由Agent（v2.0）

    基于Function Calling的分层意图识别：
    1. 识别一级（业务域）、二级（动作）、三级（子意图）
    2. 槽位提取和验证
    3. 智能澄清机制
    4. 话题切换检测（由IntentRecognitionService处理）

    Attributes:
        GREETING_RESPONSE: 问候语回复文本（类常量）
    """

    GREETING_RESPONSE: str = (
        "您好！我是您的智能客服助手，可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？"
    )

    def __init__(self) -> None:
        """初始化IntentRouterAgent。"""
        super().__init__(name="intent_router", system_prompt=None)
        from app.core.redis import get_redis_client
        self.intent_service = IntentRecognitionService(redis_client=get_redis_client())
        logger.debug("IntentRouterAgent initialized")

    async def process(self, state: dict[str, Any]) -> AgentResult:
        """处理用户输入，识别意图并路由

        流程：
        1. 接收用户查询和会话信息
        2. 识别用户意图（通过IntentRecognitionService）
        3. 验证槽位完整性
        4. 需要澄清 -> 生成追问问题
        5. 意图清晰 -> 路由到对应Agent

        Args:
            state: 路由状态字典，包含question, thread_id, user_id等字段

        Returns:
            AgentResult: 包含响应内容和更新后的状态
        """
        # Cast to RouterState for better type checking within this method
        router_state = state  # type: RouterState
        query = router_state.get("question", "")
        session_id = router_state.get("thread_id", "")
        user_id = router_state.get("user_id")

        logger.info(
            "Processing query for user_id=%s, session_id=%s, query='%s'",
            user_id, session_id, query
        )

        # 意图识别
        logger.debug("Starting intent recognition")
        result = await self.intent_service.recognize(
            query=query,
            session_id=session_id,
            conversation_history=state.get("history", []),
        )
        logger.info(
            "Intent recognized: primary=%s, confidence=%.2f",
            result.primary_intent, result.confidence
        )

        # 映射到向后兼容的意图格式
        legacy_intent = self._map_to_legacy_intent(result)
        next_agent = self._route_by_intent(result)
        logger.debug(
            "Routing decision: legacy_intent=%s, next_agent=%s",
            legacy_intent, next_agent
        )

        # 需要澄清
        if result.needs_clarification or result.missing_slots:
            logger.info("Clarification needed, missing_slots=%s", result.missing_slots)
            clarification = await self.intent_service.clarify(
                session_id=session_id,
                user_response=query,
            )
            logger.debug("Clarification response generated")
            return AgentResult(
                response=clarification.response,
                updated_state={
                    # 新格式字段
                    "intent_result": result.to_dict(),
                    "slots": result.slots or {},
                    "awaiting_clarification": True,
                    "clarification_state": clarification.state,
                    # 向后兼容字段
                    "intent": legacy_intent,
                    "next_agent": next_agent,
                }
            )

        # 意图清晰，路由到对应Agent
        # 构建更新后的状态（包含向后兼容字段）
        updated_state: RouterState = {
            # 新格式字段
            "intent_result": result.to_dict(),
            "slots": result.slots or {},
            "awaiting_clarification": result.needs_clarification,
            # 向后兼容字段（用于旧版Agent）
            "intent": legacy_intent,
            "next_agent": next_agent,
        }

        # 对于闲聊/OTHER意图，直接返回问候回复（向后兼容行为）
        if legacy_intent == Intent.OTHER:
            logger.info("OTHER intent detected, returning greeting response")
            return AgentResult(
                response=self.GREETING_RESPONSE,
                updated_state=dict(updated_state)
            )

        logger.info("Routing to agent: %s", next_agent)
        return AgentResult(
            response="",  # 由下一个Agent生成
            updated_state=dict(updated_state)
        )

    def _route_by_intent(self, result: IntentResult) -> str:
        """根据意图路由到对应Agent

        Args:
            result: 意图识别结果

        Returns:
            str: 目标Agent名称
        """
        mapping = _INTENT_MAPPINGS.get(result.primary_intent)
        target_agent = mapping["agent"] if mapping else "supervisor"
        logger.debug(
            "Routing map: primary_intent=%s -> target_agent=%s",
            result.primary_intent, target_agent
        )
        return target_agent

    def _map_to_legacy_intent(self, result: IntentResult) -> Intent:
        """将新的意图结果映射到向后兼容的Intent枚举

        Args:
            result: 意图识别结果

        Returns:
            Intent: 向后兼容的意图枚举值
        """
        mapping = _INTENT_MAPPINGS.get(result.primary_intent)
        if mapping:
            return mapping["legacy"]
        logger.warning("Unknown primary_intent=%s, defaulting to OTHER", result.primary_intent)
        return Intent.OTHER

    def _quick_intent_check(self, query: str) -> Intent:
        """快速意图检查 - 基于关键词规则匹配，不调用 LLM

        Args:
            query: 用户输入

        Returns:
            Intent: 向后兼容的意图枚举值
        """
        lowered = query.lower()

        # 问候语检测
        greetings = {"你好", "您好", "hello", "hi", "在吗", "在么"}
        if any(g in lowered for g in greetings):
            return Intent.OTHER

        # 退货/售后相关
        refund_keywords = {"退货", "退款", "售后", "退换", "换货"}
        if any(k in lowered for k in refund_keywords):
            return Intent.REFUND

        # 订单相关
        order_keywords = {"订单", "物流", "发货", "快递", "货到哪", "到哪了"}
        if any(k in lowered for k in order_keywords):
            return Intent.ORDER

        # 政策相关（作为粗略分类）
        policy_keywords = {"政策", "规则", "怎么算", "多少钱", "价格", "运费"}
        if any(k in lowered for k in policy_keywords):
            return Intent.POLICY

        return Intent.OTHER


# 向后兼容别名
RouterAgent = IntentRouterAgent
