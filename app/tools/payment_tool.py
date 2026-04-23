import logging
from contextlib import nullcontext
from datetime import datetime

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import select

from app.core.database import async_session_maker
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class PaymentTool(BaseTool):
    name = "payment"
    description = "查询支付状态、发票信息、退款记录"

    async def execute(self, state: AgentState, session=None, **kwargs) -> ToolResult:
        user_id = state.get("user_id")
        slots = state.get("slots") or {}
        order_sn = slots.get("order_sn") or kwargs.get("order_sn")

        refund_records: list[dict] = []
        payment_status = "未知"
        invoice_status = "未查询到发票信息"

        session_cm = nullcontext(session) if session is not None else async_session_maker()
        try:
            async with session_cm as sess:
                target_order_id: int | None = None
                if order_sn:
                    order_stmt = select(Order).where(
                        Order.order_sn == order_sn, Order.user_id == user_id
                    )
                    order_result = await sess.exec(order_stmt)
                    order = order_result.one_or_none()

                    if order:
                        payment_status = (
                            "已支付" if order.status == OrderStatus.PAID else str(order.status)
                        )
                        invoice_status = "已开票"
                        target_order_id = order.id

                    refund_stmt = select(RefundApplication).where(
                        RefundApplication.user_id == user_id,
                        RefundApplication.order_id == target_order_id,
                    )
                else:
                    refund_stmt = select(RefundApplication).where(
                        RefundApplication.user_id == user_id
                    )

                refund_result = await sess.exec(refund_stmt)
                refunds: list[RefundApplication] = list(refund_result.all())

                for refund in refunds:
                    status_value = str(refund.status)
                    if hasattr(refund.status, "value"):
                        status_value = str(refund.status.value)

                    created_at_str = str(refund.created_at)
                    if isinstance(refund.created_at, datetime):
                        created_at_str = refund.created_at.strftime("%Y-%m-%d %H:%M:%S")

                    refund_records.append(
                        {
                            "refund_id": refund.id,
                            "order_sn": order_sn,
                            "amount": float(refund.refund_amount),
                            "status": status_value,
                            "created_at": created_at_str,
                        }
                    )
        except (SQLAlchemyError, OperationalError):
            logger.exception("[PaymentTool] 查询支付/退款记录失败")
            return ToolResult(
                output={
                    "payment_status": "未知",
                    "invoice_status": "未查询到发票信息",
                    "refund_records": [],
                    "message": "查询失败，请稍后重试",
                }
            )

        if not refund_records and payment_status == "未知":
            return ToolResult(
                output={
                    "payment_status": payment_status,
                    "invoice_status": invoice_status,
                    "refund_records": [],
                    "message": "未查询到相关支付/退款记录",
                }
            )

        return ToolResult(
            output={
                "payment_status": payment_status,
                "invoice_status": invoice_status,
                "refund_records": refund_records,
            }
        )
