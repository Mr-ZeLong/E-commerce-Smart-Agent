import logging
from typing import Any

from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlmodel import select

from app.agents.base import AgentResult, BaseAgent
from app.core.database import async_session_maker
from app.models.order import Order
from app.models.refund import RefundApplication
from app.services.refund_service import RefundRiskService, get_order_by_sn, process_refund_for_order
from app.tasks.refund_tasks import notify_admin_audit
from app.utils.order_utils import classify_refund_reason, extract_order_sn

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

    def __init__(self):
        super().__init__(
            name="order",
            system_prompt=ORDER_SYSTEM_PROMPT
        )

    async def process(self, state: dict[str, Any]) -> AgentResult:
        """处理订单相关请求"""
        question = state.get("question", "")
        user_id = state.get("user_id")
        intent = state.get("intent")

        if user_id is None:
            return AgentResult(
                response="抱歉，无法识别用户身份，请重新登录。",
                updated_state={"order_data": None}
            )

        if intent == "REFUND":
            thread_id = state.get("thread_id", "")
            return await self._handle_refund(question, user_id, thread_id)
        else:
            return await self._handle_order_query(question, user_id)

    async def _handle_order_query(
        self,
        question: str,
        user_id: int
    ) -> AgentResult:
        """处理订单查询"""
        order_sn = extract_order_sn(question)
        order_data = await self._query_order(order_sn, user_id)

        if not order_data:
            return AgentResult(
                response="抱歉，未找到相关订单信息。请确认订单号是否正确，或尝试查询'我的订单'。",
                updated_state={"order_data": None}
            )

        response = self._format_order_response(order_data)

        return AgentResult(
            response=response,
            updated_state={"order_data": order_data}
        )

    async def _handle_refund(
        self,
        question: str,
        user_id: int,
        thread_id: str = ""
    ) -> AgentResult:
        """处理退货申请"""
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

            updated_state = {
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

    async def _query_order(
        self,
        order_sn: str | None,
        user_id: int
    ) -> dict | None:
        """查询订单"""
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
            logger.exception("[OrderAgent] Database error querying order")
            raise
        except Exception:
            logger.exception("[OrderAgent] Unexpected error querying order")
            return None

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
