import logging
from typing import Any

from app.agents.base import AgentResult, BaseAgent
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
    """
    订单专家 Agent

    职责：
    1. 查询订单状态和信息
    2. 处理退货申请流程
    3. 检查退货资格
    """

    def __init__(self, order_service: OrderService | None = None):
        super().__init__(name="order", system_prompt=ORDER_SYSTEM_PROMPT)
        self.order_service = order_service or OrderService()

    async def process(self, state: dict[str, Any]) -> AgentResult:
        """处理订单相关请求"""
        question = state.get("question", "")
        user_id = state.get("user_id")
        intent = state.get("intent")

        if user_id is None:
            return AgentResult(
                response="抱歉，无法识别用户身份，请重新登录。", updated_state={"order_data": None}
            )

        if intent == "REFUND":
            thread_id = state.get("thread_id", "")
            return await self._handle_refund(question, user_id, thread_id)
        else:
            return await self._handle_order_query(question, user_id)

    async def _handle_order_query(self, question: str, user_id: int) -> AgentResult:
        """处理订单查询"""
        order_sn = extract_order_sn(question)
        order_data = await self.order_service.get_order_for_user(order_sn, user_id)

        if not order_data:
            return AgentResult(
                response="抱歉，未找到相关订单信息。请确认订单号是否正确，或尝试查询'我的订单'。",
                updated_state={"order_data": None},
            )

        response = self._format_order_response(order_data)

        return AgentResult(response=response, updated_state={"order_data": order_data})

    async def _handle_refund(self, question: str, user_id: int, thread_id: str = "") -> AgentResult:
        """处理退货申请"""
        return await self.order_service.handle_refund_request(
            question=question, user_id=user_id, thread_id=thread_id
        )

    def _format_order_response(self, order: dict) -> str:
        """格式化订单回复"""
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
