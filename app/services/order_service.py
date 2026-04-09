import logging
from typing import Any

from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlmodel import select

from app.core.database import async_session_maker
from app.models.order import Order
from app.models.refund import RefundApplication
from app.services.refund_service import (
    RefundRiskService,
    get_order_by_sn,
    process_refund_for_order,
)
from app.tasks.refund_tasks import notify_admin_audit
from app.utils.order_utils import classify_refund_reason, extract_order_sn


logger = logging.getLogger(__name__)


class OrderService:
    """订单服务层：封装订单查询与退款申请的数据库交互和副作用"""

    async def get_order_for_user(
        self,
        order_sn: str | None,
        user_id: int
    ) -> dict | None:
        """查询用户订单，返回序列化后的字典或 None。"""
        try:
            async with async_session_maker() as session:
                if order_sn:
                    order = await get_order_by_sn(order_sn, user_id, session)
                else:
                    stmt = (
                        select(Order)
                        .where(Order.user_id == user_id)
                        .order_by(Order.created_at.desc())  # type: ignore
                        .limit(1)
                    )
                    result = await session.exec(stmt)
                    order = result.first()

                return order.model_dump() if order else None
        except NoResultFound:
            return None
        except SQLAlchemyError:
            logger.exception("[OrderService] Database error querying order")
            return None
        except Exception:
            logger.exception("[OrderService] Unexpected error querying order")
            return None

    async def handle_refund_request(
        self,
        question: str,
        user_id: int,
        thread_id: str = ""
    ) -> "AgentResult":
        """处理退货申请，封装数据库事务与 Celery 副作用。"""
        from app.agents.base import AgentResult

        order_sn = extract_order_sn(question)

        if not order_sn:
            return AgentResult(
                response="请提供订单号以便处理退货申请。例如：我要退货，订单号 SN20240001",
                updated_state={"refund_flow_active": False}
            )

        reason_category = classify_refund_reason(question)
        reason_detail = reason_category.value if reason_category else question

        async with async_session_maker() as session:
            order = await get_order_by_sn(order_sn, user_id, session)
            if not order:
                return AgentResult(
                    response=f"未找到订单 {order_sn}，请确认订单号是否正确。",
                    updated_state={"refund_flow_active": False}
                )

            if order.id is None:
                return AgentResult(
                    response="订单数据异常，请稍后重试。",
                    updated_state={"refund_flow_active": False}
                )

            success, message, refund_data = await process_refund_for_order(
                order_sn=order_sn,
                user_id=user_id,
                reason_detail=reason_detail,
                reason_category=reason_category,
                session=session
            )

            if not success:
                return AgentResult(
                    response=message,
                    updated_state={
                        "order_data": order.model_dump(),
                        "refund_flow_active": False
                    }
                )

            # 退款申请创建成功后，执行风控审计
            audit = None
            if refund_data is not None:
                refund_result = await session.exec(
                    select(RefundApplication).where(RefundApplication.id == refund_data["refund_id"])
                )
                refund = refund_result.one_or_none()
                if refund:
                    audit = await RefundRiskService.assess_and_create_audit(
                        session, refund, order, user_id, thread_id
                    )

            updated_state: dict[str, Any] = {
                "order_data": order.model_dump(),
                "refund_flow_active": True
            }
            if refund_data is not None:
                updated_state["refund_data"] = {
                    "refund_id": refund_data["refund_id"],
                    "amount": refund_data["amount"]
                }

            await session.commit()

            # 事务提交成功后，再派发 Celery 通知任务
            if audit is not None:
                notify_admin_audit.delay(audit.id)

            return AgentResult(
                response=f"✅ {message}",
                updated_state=updated_state
            )
