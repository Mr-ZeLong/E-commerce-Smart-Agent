import re

from sqlmodel import select

from app.agents.base import AgentResult, BaseAgent
from app.core.database import async_session_maker
from app.models.order import Order
from app.models.refund import RefundReason
from app.services.refund_service import RefundApplicationService, RefundEligibilityChecker

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

    async def process(self, state: dict) -> AgentResult:
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
            return await self._handle_refund(question, user_id)
        else:
            return await self._handle_order_query(question, user_id)

    async def _handle_order_query(
        self,
        question: str,
        user_id: int
    ) -> AgentResult:
        """处理订单查询"""
        # 提取订单号
        order_sn = self._extract_order_sn(question)

        # 查询订单
        order_data = await self._query_order(order_sn, user_id)

        if not order_data:
            return AgentResult(
                response="抱歉，未找到相关订单信息。请确认订单号是否正确，或尝试查询'我的订单'。",
                updated_state={"order_data": None}
            )

        # 生成回复
        response = self._format_order_response(order_data)

        return AgentResult(
            response=response,
            updated_state={"order_data": order_data}
        )

    async def _handle_refund(
        self,
        question: str,
        user_id: int
    ) -> AgentResult:
        """处理退货申请"""
        # 提取订单号
        order_sn = self._extract_order_sn(question)

        if not order_sn:
            return AgentResult(
                response="请提供订单号以便处理退货申请。例如：我要退货，订单号 SN20240001",
                updated_state={"refund_flow_active": False}
            )

        # 提取退货原因
        reason_detail = question
        reason_category = self._classify_refund_reason(question)

        # 查询订单
        async with async_session_maker() as session:
            stmt = select(Order).where(
                Order.order_sn == order_sn.upper(),
                Order.user_id == user_id
            )
            result = await session.exec(stmt)
            order = result.first()

            if not order:
                return AgentResult(
                    response=f"未找到订单 {order_sn}，请确认订单号是否正确。",
                    updated_state={"refund_flow_active": False}
                )

            # 检查退货资格
            is_eligible, eligibility_msg = await RefundEligibilityChecker.check_eligibility(
                order, session
            )

            if not is_eligible:
                return AgentResult(
                    response=f"该订单不符合退货条件：{eligibility_msg}",
                    updated_state={
                        "order_data": order.model_dump(),
                        "refund_flow_active": False
                    }
                )

            # 创建退货申请
            success, message, refund_app = await RefundApplicationService.create_refund_application(
                order_id=order.id,
                user_id=user_id,
                reason_detail=reason_detail,
                reason_category=reason_category,
                session=session
            )

            if success and refund_app is not None:
                return AgentResult(
                    response=f"✅ {message}",
                    updated_state={
                        "order_data": order.model_dump(),
                        "refund_data": {
                            "refund_id": refund_app.id,
                            "amount": float(refund_app.refund_amount)
                        },
                        "refund_flow_active": True
                    }
                )
            elif success:
                return AgentResult(
                    response=f"✅ {message}",
                    updated_state={
                        "order_data": order.model_dump(),
                        "refund_flow_active": True
                    }
                )
            else:
                return AgentResult(
                    response=f"❌ {message}",
                    updated_state={"refund_flow_active": False}
                )

    def _extract_order_sn(self, text: str) -> str | None:
        """提取订单号"""
        match = re.search(r'(SN\d+)', text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def _classify_refund_reason(self, text: str) -> RefundReason:
        """分类退货原因"""
        if "质量" in text or "破损" in text:
            return RefundReason.QUALITY_ISSUE
        elif "尺码" in text or "大小" in text or "不合适" in text:
            return RefundReason.SIZE_NOT_FIT
        elif "不符" in text or "描述" in text:
            return RefundReason.NOT_AS_DESCRIBED
        else:
            return RefundReason.OTHER

    async def _query_order(
        self,
        order_sn: str | None,
        user_id: int
    ) -> dict | None:
        """查询订单"""
        try:
            async with async_session_maker() as session:
                if order_sn:
                    stmt = select(Order).where(
                        Order.order_sn == order_sn,
                        Order.user_id == user_id
                    )
                else:
                    # 查询最近订单
                    stmt = (
                        select(Order)
                        .where(Order.user_id == user_id)
                        .order_by(Order.created_at.desc())  # type: ignore
                        .limit(1)
                    )

                result = await session.exec(stmt)
                order = result.first()

                return order.model_dump() if order else None
        except Exception as e:
            print(f"[OrderAgent] Database query failed: {e}")
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
