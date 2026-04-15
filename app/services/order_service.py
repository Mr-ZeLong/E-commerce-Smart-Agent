from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import async_session_maker
from app.models.order import Order
from app.models.state import AgentProcessResult
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

    async def _get_order_for_user_body(
        self, order_sn: str | None, user_id: int, session: AsyncSession
    ) -> dict | None:
        if order_sn:
            order = await get_order_by_sn(order_sn, user_id, session)
        else:
            stmt = (
                select(Order)
                .where(Order.user_id == user_id)
                .order_by(desc(Order.created_at))
                .limit(1)
            )
            result = await session.exec(stmt)
            order = result.first()

        return order.model_dump() if order else None

    async def get_order_for_user(
        self, order_sn: str | None, user_id: int, session: AsyncSession | None = None
    ) -> dict | None:
        """查询用户订单，返回序列化后的字典或 None。"""
        try:
            if session is None:
                async with async_session_maker() as session:
                    return await self._get_order_for_user_body(order_sn, user_id, session)
            return await self._get_order_for_user_body(order_sn, user_id, session)
        except SQLAlchemyError:
            logger.exception("[OrderService] Database error querying order")
            raise

    async def _handle_refund_request_body(
        self, question: str, user_id: int, thread_id: str, session: AsyncSession
    ) -> AgentProcessResult:
        order_sn = extract_order_sn(question)

        if not order_sn:
            return {
                "response": "请提供订单号以便处理退货申请。例如：我要退货，订单号 SN20240001",
                "updated_state": {"refund_flow_active": False},
            }

        reason_category = classify_refund_reason(question)
        reason_detail = question

        order = await get_order_by_sn(order_sn, user_id, session)
        if not order:
            return {
                "response": f"未找到订单 {order_sn}，请确认订单号是否正确。",
                "updated_state": {"refund_flow_active": False},
            }

        if order.id is None:
            return {
                "response": "订单数据异常，请稍后重试。",
                "updated_state": {"refund_flow_active": False},
            }

        success, message, refund_data, refund_app = await process_refund_for_order(
            order_sn=order_sn,
            user_id=user_id,
            reason_detail=reason_detail,
            reason_category=reason_category,
            session=session,
            order=order,
        )

        if not success:
            return {
                "response": message,
                "updated_state": {
                    "order_data": order.model_dump(),
                    "refund_flow_active": False,
                },
            }

        audit = None
        if refund_app is not None:
            audit = await RefundRiskService.assess_and_create_audit(
                session, refund_app, order, user_id, thread_id
            )

        updated_state: dict[str, Any] = {
            "order_data": order.model_dump(),
            "refund_flow_active": True,
        }
        if refund_data is not None:
            updated_state["refund_data"] = {
                "refund_id": refund_data["refund_id"],
                "amount": refund_data["amount"],
            }

        await session.commit()

        # 事务提交成功后，再派发 Celery 通知任务
        if audit is not None:
            notify_admin_audit.delay(audit.id)

        return {"response": f"✅ {message}", "updated_state": updated_state}

    async def handle_refund_request(
        self, question: str, user_id: int, thread_id: str = "", session: AsyncSession | None = None
    ) -> AgentProcessResult:
        """处理退货申请，封装数据库事务与 Celery 副作用。"""
        try:
            if session is None:
                async with async_session_maker() as session:
                    return await self._handle_refund_request_body(
                        question, user_id, thread_id, session
                    )
            return await self._handle_refund_request_body(question, user_id, thread_id, session)
        except SQLAlchemyError:
            logger.exception("[OrderService] Database error handling refund request")
            raise
