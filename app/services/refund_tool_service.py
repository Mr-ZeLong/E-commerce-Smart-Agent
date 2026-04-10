"""
Refund Tool Service: 封装 LangGraph Tools 所需的数据库交互与业务逻辑
"""

from sqlmodel import select

from app.core.database import async_session_maker
from app.models.order import Order
from app.models.refund import RefundReason
from app.services.refund_service import (
    RefundApplicationService,
    RefundEligibilityChecker,
    get_order_by_sn,
    process_refund_for_order,
)


async def check_refund_eligibility(order_sn: str, user_id: int) -> str:
    """检查订单是否符合退货条件。"""
    async with async_session_maker() as session:
        order = await get_order_by_sn(order_sn, user_id, session)

        if not order:
            return f"❌ 未找到订单 {order_sn}，或您无权访问此订单。"

        is_eligible, message = await RefundEligibilityChecker.check_eligibility(order, session)

        if is_eligible:
            return (
                f"✅ 订单 {order_sn} 符合退货条件。\n"
                f"订单信息：\n"
                f"  - 商品：{', '.join([item['name'] for item in order.items])}\n"
                f"  - 金额：¥{order.total_amount}\n"
                f"  - 状态：{order.status}\n"
                f"检查结果：{message}"
            )
        else:
            return f"❌ 订单 {order_sn} 不符合退货条件。\n拒绝原因：{message}"


async def submit_refund_application(
    order_sn: str, user_id: int, reason_detail: str, reason_category: str | None = None
) -> str:
    """提交退货申请。"""
    async with async_session_maker() as session:
        category = None
        if reason_category:
            try:
                category = RefundReason(reason_category)
            except ValueError:
                category = RefundReason.OTHER

        success, message, refund_data = await process_refund_for_order(
            order_sn=order_sn,
            user_id=user_id,
            reason_detail=reason_detail,
            reason_category=category,
            session=session,
        )

        if success and refund_data:
            return (
                f"✅ 退货申请提交成功！\n\n"
                f"📋 申请信息：\n"
                f"  - 申请编号：#{refund_data['refund_id']}\n"
                f"  - 订单号：{order_sn}\n"
                f"  - 退款金额：¥{refund_data['amount']}\n"
                f"  - 申请状态：{refund_data['status']}（待审核）\n"
                f"  - 退货原因：{refund_data['reason_detail']}\n\n"
                f"⏳ 后续流程：\n"
                f"  1. 我们会在 1-2 个工作日内审核您的申请\n"
                f"  2. 审核通过后，请将商品寄回（保持包装完好）\n"
                f"  3. 收到退货后，我们会在 3-5 个工作日内完成退款\n\n"
                f"💡 温馨提示：您可以随时查询申请进度。"
            )
        else:
            return f"❌ 退货申请失败。\n原因：{message}"


async def query_refund_status(user_id: int, refund_id: int | None = None) -> str:
    """查询退货申请状态。"""
    async with async_session_maker() as session:
        if refund_id:
            refund = await RefundApplicationService.get_refund_by_id(
                refund_id=refund_id, user_id=user_id, session=session
            )

            if not refund:
                return f"❌ 未找到申请编号 #{refund_id}，或您无权访问此申请。"

            stmt = select(Order).where(Order.id == refund.order_id)
            result = await session.exec(stmt)
            order = result.first()

            return (
                f"📋 退货申请详情（#{refund.id}）\n\n"
                f"订单信息：\n"
                f"  - 订单号：{order.order_sn if order else '未知'}\n"
                f"  - 商品："
                f"{', '.join([item['name'] for item in order.items]) if order else '未知'}\n\n"
                f"申请信息：\n"
                f"  - 申请状态：{refund.status}\n"
                f"  - 退款金额：¥{refund.refund_amount}\n"
                f"  - 申请时间：{refund.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"  - 退货原因：{refund.reason_detail}\n\n"
                f"{
                    (
                        '审核信息：\n  - 审核时间：' + refund.reviewed_at.strftime('%Y-%m-%d %H:%M')
                        if refund.reviewed_at
                        else '⏳ 审核中，请耐心等待'
                    )
                }\n"
                f"{('  - 审核备注：' + refund.admin_note) if refund.admin_note else ''}"
            )

        else:
            refund_list = await RefundApplicationService.get_user_refund_applications(
                user_id=user_id, session=session
            )

            if not refund_list:
                return "📭 您还没有退货申请记录。"

            result_text = f"📋 您的退货申请列表（共 {len(refund_list)} 条）\n\n"

            for refund in refund_list:
                stmt = select(Order).where(Order.id == refund.order_id)
                order_result = await session.exec(stmt)
                order = order_result.first()

                status_emoji = {
                    "PENDING": "⏳",
                    "APPROVED": "✅",
                    "REJECTED": "❌",
                    "COMPLETED": "🎉",
                    "CANCELLED": "🚫",
                }.get(refund.status, "❓")

                result_text += (
                    f"{status_emoji} 申请 #{refund.id}\n"
                    f"  订单号：{order.order_sn if order else '未知'}\n"
                    f"  状态：{refund.status}\n"
                    f"  金额：¥{refund.refund_amount}\n"
                    f"  申请时间：{refund.created_at.strftime('%Y-%m-%d')}\n\n"
                )

            return result_text.strip()
