from sqlmodel import select

from app.core.database import async_session_maker
from app.models.order import Order
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult


class LogisticsTool(BaseTool):
    name = "logistics"
    description = "查询订单物流状态"

    async def execute(self, state: AgentState, **kwargs) -> ToolResult:
        slots = state.get("slots") or {}
        order_sn = slots.get("order_sn") or kwargs.get("order_sn")
        user_id = state.get("user_id")

        async with async_session_maker() as session:
            result = await session.exec(
                select(Order).where(Order.order_sn == order_sn, Order.user_id == user_id)
            )
            order = result.one_or_none()

        if order:
            return ToolResult(
                output={
                    "tracking_number": order.tracking_number or "暂无",
                    "carrier": "顺丰速运",
                    "status": "运输中",
                    "latest_update": "快件已到达【北京顺义集散中心】",
                    "estimated_delivery": "2024-01-20",
                }
            )

        return ToolResult(output={"status": "未找到订单"})
