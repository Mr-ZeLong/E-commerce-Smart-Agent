import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.models.state import AgentProcessResult, AgentState
from app.services.order_service import OrderService
from app.utils.order_utils import extract_order_sn

logger = logging.getLogger(__name__)

ORDER_SYSTEM_PROMPT = """你是专业的电商订单处理助手。

规则：
1. 准确查询订单信息，清晰列出订单号、状态、金额
2. 处理退货申请时，先检查资格再提交
3. 订单数据必须来自数据库，严禁编造
4. 语气友好，解答用户疑问"""


class OrderAgent(BaseAgent):
    """订单专家 Agent"""

    def __init__(self, order_service: OrderService, llm: BaseChatModel):
        super().__init__(name="order_agent", llm=llm, system_prompt=ORDER_SYSTEM_PROMPT)
        self.order_service = order_service

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        question = state.get("question", "")
        user_id = state.get("user_id")
        intent_result = state.get("intent_result") or {}
        if user_id is None:
            return {
                "response": "抱歉，无法识别用户身份，请重新登录。",
                "updated_state": {"order_data": None},
            }

        if (
            intent_result.get("tertiary_intent") == "REFUND"
            or intent_result.get("primary_intent") == "AFTER_SALES"
        ):
            thread_id = state.get("thread_id", "")
            result = await self._handle_refund(question, user_id, thread_id)
            return result
        else:
            result = await self._handle_order_query(question, user_id)
            return result

    async def _handle_order_query(self, question: str, user_id: int) -> AgentProcessResult:
        order_sn = extract_order_sn(question)
        order_data = await self.order_service.get_order_for_user(order_sn, user_id)

        if not order_data:
            return {
                "response": "抱歉，未找到相关订单信息。请确认订单号是否正确，或尝试查询'我的订单'。",
                "updated_state": {"order_data": None},
            }

        response = self._format_order_response(order_data)
        return {"response": response, "updated_state": {"order_data": order_data}}

    async def _handle_refund(
        self, question: str, user_id: int, thread_id: str = ""
    ) -> AgentProcessResult:
        return await self.order_service.handle_refund_request(
            question=question, user_id=user_id, thread_id=thread_id
        )

    def _format_order_response(self, order: dict) -> str:
        items = order.get("items", [])
        items_str = ", ".join([f"{i.get('name', '商品')}x{i.get('qty', 1)}" for i in items])

        return (
            f"📦 订单信息：\n"
            f"订单号: {order.get('order_sn', 'N/A')}\n"
            f"状态: {order.get('status', 'N/A')}\n"
            f"商品: {items_str}\n"
            f"金额: ¥{order.get('total_amount', 0)}\n"
            f"物流单号: {order.get('tracking_number', '暂无')}"
        )
