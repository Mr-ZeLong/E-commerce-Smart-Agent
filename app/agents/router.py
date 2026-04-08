"""新的意图路由Agent

使用分层意图识别系统替换原有的规则+LLM混合方案。
"""

from enum import Enum

from app.agents.base import AgentResult, BaseAgent
from app.intent import IntentRecognitionService
from app.intent.models import IntentCategory, IntentResult


class Intent(str, Enum):
    """意图枚举（向后兼容）"""
    ORDER = "ORDER"
    POLICY = "POLICY"
    REFUND = "REFUND"
    OTHER = "OTHER"


class IntentRouterAgent(BaseAgent):
    """
    意图路由Agent（v2.0）

    基于Function Calling的分层意图识别：
    1. 识别一级（业务域）、二级（动作）、三级（子意图）
    2. 槽位提取和验证
    3. 智能澄清机制
    4. 话题切换检测
    """

    def __init__(self):
        super().__init__(name="intent_router", system_prompt=None)
        self.intent_service = IntentRecognitionService()

    async def process(self, state: dict) -> AgentResult:
        """
        处理用户输入，识别意图并路由

        流程：
        1. 检测话题切换
        2. 识别用户意图（Function Calling）
        3. 验证槽位完整性
        4. 需要澄清 -> 生成追问问题
        5. 意图清晰 -> 路由到对应Agent
        """
        query = state.get("question", "")
        session_id = state.get("thread_id", "")
        user_id = state.get("user_id")

        # 1. 话题切换检测
        if await self._detect_topic_switch(state):
            await self._handle_topic_switch(session_id)

        # 2. 意图识别
        result = await self.intent_service.recognize(
            query=query,
            session_id=session_id,
            conversation_history=state.get("history", []),
        )

        # 映射到向后兼容的意图格式
        legacy_intent = self._map_to_legacy_intent(result)
        next_agent = self._route_by_intent(result)

        # 3. 需要澄清
        if result.needs_clarification or result.missing_slots:
            clarification = await self.intent_service.clarify(
                session_id=session_id,
                user_response=query,
            )
            return AgentResult(
                response=clarification.response,
                updated_state={
                    # 新格式字段
                    "intent_result": result.to_dict(),
                    "slots": result.slots,
                    "awaiting_clarification": True,
                    "clarification_state": clarification.state,
                    # 向后兼容字段
                    "intent": legacy_intent,
                    "next_agent": next_agent,
                }
            )

        # 4. 意图清晰，路由到对应Agent
        # 构建更新后的状态（包含向后兼容字段）
        updated_state = {
            # 新格式字段
            "intent_result": result.to_dict(),
            "slots": result.slots,
            "awaiting_clarification": result.needs_clarification,
            # 向后兼容字段（用于旧版Agent）
            "intent": legacy_intent,
            "next_agent": next_agent,
        }

        # 对于闲聊/OTHER意图，直接返回问候回复（向后兼容行为）
        if legacy_intent == Intent.OTHER:
            return AgentResult(
                response="您好！我是您的智能客服助手，可以帮您查询订单、咨询政策或处理退货。请问有什么可以帮您？",
                updated_state=updated_state
            )

        return AgentResult(
            response="",  # 由下一个Agent生成
            updated_state=updated_state
        )

    def _quick_intent_check(self, question: str) -> Intent | None:
        """
        快速意图检查（规则匹配，向后兼容）

        注意：此方法仅用于向后兼容。新系统使用 IntentRecognitionService
        进行完整的意图识别。此方法提供基于规则的快速匹配。
        """
        q = question.lower()

        # 退货关键词
        refund_keywords = ["退货", "退款", "退钱", "不要了", "换货"]
        if any(kw in q for kw in refund_keywords):
            return Intent.REFUND

        # 订单关键词
        order_keywords = ["订单", "物流", "到哪了", "快递", "发货", "签收", "sn"]
        if any(kw in q for kw in order_keywords):
            return Intent.ORDER

        # 简单的问候检测
        greeting_keywords = ["你好", "您好", "hi", "hello", "在吗"]
        if any(q.strip().startswith(kw) for kw in greeting_keywords) and len(q) < 10:
            return Intent.OTHER

        return None

    def _route_by_intent(self, result: IntentResult) -> str:
        """根据意图路由到对应Agent"""
        routing_map = {
            IntentCategory.ORDER: "order",
            IntentCategory.AFTER_SALES: "order",
            IntentCategory.POLICY: "policy",
            IntentCategory.PRODUCT: "policy",  # 商品咨询也走policy
            IntentCategory.RECOMMENDATION: "policy",
            IntentCategory.CART: "order",
        }
        return routing_map.get(result.primary_intent, "supervisor")

    def _map_to_legacy_intent(self, result: IntentResult) -> Intent:
        """将新的意图结果映射到向后兼容的Intent枚举"""
        primary = result.primary_intent

        # 退货/售后相关意图映射到 REFUND
        if primary == IntentCategory.AFTER_SALES:
            return Intent.REFUND

        # 订单相关意图
        if primary == IntentCategory.ORDER:
            return Intent.ORDER

        # 购物车相关也映射到 ORDER（由OrderAgent处理）
        if primary == IntentCategory.CART:
            return Intent.ORDER

        # 政策、商品、推荐等映射到 POLICY
        if primary in (IntentCategory.POLICY, IntentCategory.PRODUCT, IntentCategory.RECOMMENDATION):
            return Intent.POLICY

        # 其他/未知意图映射到 OTHER
        if primary == IntentCategory.OTHER:
            return Intent.OTHER

        # 默认回退
        return Intent.OTHER

    async def _detect_topic_switch(self, state: dict) -> bool:
        """检测话题切换（简化版）"""
        # 实际实现应该使用 topic_switch_detector
        # 这里简化处理
        return False

    async def _handle_topic_switch(self, session_id: str):
        """处理话题切换"""
        # 实际实现应该重置会话状态
        pass


# 向后兼容别名
RouterAgent = IntentRouterAgent
