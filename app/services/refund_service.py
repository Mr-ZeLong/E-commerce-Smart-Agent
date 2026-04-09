# app/services/refund_service.py
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundReason, RefundStatus

# ==========================================
# 退货规则配置（硬编码业务规则）
# ==========================================

class RefundRules:
    """退货规则常量"""

    # 退货期限（天数）
    REFUND_DEADLINE_DAYS = 7

    # 允许退货的订单状态
    ALLOWED_ORDER_STATUSES = [
        OrderStatus.DELIVERED,  # 已签收
        OrderStatus.SHIPPED     # 已发货（可选，根据业务决定）
    ]

    # 不可退货的商品类别（预留，后续可扩展）
    NON_REFUNDABLE_CATEGORIES = [
        "内衣",  # 贴身衣物
        "食品",  # 食品类
        "定制商品"  # 定制类
    ]


# ==========================================
# 退货资格校验引擎
# ==========================================

class RefundEligibilityChecker:
    """退货资格校验器（纯 Python 硬逻辑，不依赖 LLM）"""

    @staticmethod
    async def check_eligibility(
        order: Order,
        session: AsyncSession
    ) -> tuple[bool, str]:
        """
        检查订单是否可以退货

        返回:
            (是否可退货, 原因说明)
        """

        # ========== 规则 1: 检查订单状态 ==========
        if order.status not in RefundRules.ALLOWED_ORDER_STATUSES:
            return False, f"订单状态为 {order.status}，只有已发货或已签收的订单才能退货"

        # ========== 规则 2: 检查是否已有退货申请 ==========
        existing_refund = await RefundEligibilityChecker._check_existing_refund(
            order.id, session  # ty:ignore[invalid-argument-type]
        )
        if existing_refund:
            return False, f"该订单已存在退货申请（状态：{existing_refund. status}）"

        # ========== 规则 3: 检查退货时效 ==========
        # 以订单创建时间或签收时间为准（这里用 created_at，实际应该用 delivered_at）
        time_limit_check, time_msg = RefundEligibilityChecker._check_time_limit(order)
        if not time_limit_check:
            return False, time_msg

        # ========== 规则 4: 检查商品类别（预留） ==========
        category_check, category_msg = RefundEligibilityChecker._check_category(order)
        if not category_check:
            return False, category_msg

        # ========== 所有规则通过 ==========
        return True, "订单符合退货条件"

    @staticmethod
    async def _check_existing_refund(
        order_id:  int,
        session: AsyncSession
    ) -> RefundApplication | None:
        """检查是否已有退货申请"""
        stmt = select(RefundApplication).where(
            RefundApplication.order_id == order_id,
            RefundApplication.status. in_([  # type: ignore
                RefundStatus. PENDING,
                RefundStatus. APPROVED
            ])
        )
        result = await session.exec(stmt)
        return result. first()

    @staticmethod
    def _check_time_limit(order: Order) -> tuple[bool, str]:
        """检查退货时效"""
        now = datetime.now(UTC)

        # 计算订单创建后的天数
        # 注意：这里应该用 delivered_at（签收时间），但示例数据没有这个字段
        # 实际业务中需要在 Order 模型中添加 delivered_at 字段
        order_time = order.created_at
        if order_time.tzinfo is None:
            # 如果 order_time 是 naive，假设它是 UTC
            order_time = order_time.replace(tzinfo=UTC)
        days_passed = (now - order_time).days

        if days_passed > RefundRules.REFUND_DEADLINE_DAYS:
            return False, (
                f"订单已超过退货期限（{RefundRules.REFUND_DEADLINE_DAYS}天），"
                f"当前已过 {days_passed} 天"
            )

        return True, f"在退货期限内（已过 {days_passed} 天）"

    @staticmethod
    def _check_category(order:  Order) -> tuple[bool, str]:
        """检查商品类别（预留扩展）"""
        # 检查订单中是否包含不可退货的商品
        for item in order.items:
            item_name = item.get("name", "")

            # 简单的字符串匹配（实际应该用商品分类字段）
            for non_refundable in RefundRules.NON_REFUNDABLE_CATEGORIES:
                if non_refundable in item_name:
                    return False, f"订单包含不可退货商品：{item_name}（{non_refundable}类商品不支持退货）"

        return True, "商品类别符合退货条件"


# ==========================================
# 退货申请创建服务
# ==========================================

class RefundApplicationService:
    """退货申请服务"""

    @staticmethod
    async def create_refund_application(
        order_id: int,
        user_id: int,
        reason_detail: str,
        reason_category: RefundReason | None,
        session: AsyncSession
    ) -> tuple[bool, str, RefundApplication | None]:
        """
        创建退货申请

        参数:
            order_id:  订单ID
            user_id: 用户ID
            reason_detail:  退货原因详细描述
            reason_category: 退货原因分类
            session: 数据库会话

        返回:
            (是否成功, 消息, 退货申请对象)
        """

        # ========== 步骤 1: 查询订单 ==========
        stmt = select(Order).where(
            Order.id == order_id,
            Order.user_id == user_id  # 🔒 安全校验：只能退自己的订单
        )
        result = await session.exec(stmt)
        order = result.first()

        if not order:
            return False, "订单不存在或无权访问", None

        # ========== 步骤 2: 资格校验 ==========
        is_eligible, eligibility_msg = await RefundEligibilityChecker.check_eligibility(
            order, session
        )

        if not is_eligible:
            return False, f"退货申请被拒绝：{eligibility_msg}", None

        # ========== 步骤 3: 创建退货申请记录 ==========
        refund_app = RefundApplication(
            order_id=order_id,
            user_id=user_id,
            status=RefundStatus.PENDING,
            reason_category=reason_category,
            reason_detail=reason_detail,
            refund_amount=order.total_amount,  # 默认全额退款
        )

        session.add(refund_app)

        # ========== 步骤 4: 刷新记录以获取 ID ==========
        try:
            await session.flush()
            await session.refresh(refund_app)

            return True, f"退货申请已提交（申请编号：{refund_app.id}），等待审核", refund_app

        except Exception as e:
            return False, f"提交失败：{str(e)}", None

    @staticmethod
    async def get_user_refund_applications(
        user_id: int,
        session: AsyncSession,
        status: RefundStatus | None = None
    ) -> list[RefundApplication]:
        """
        查询用户的退货申请列表

        参数:
            user_id: 用户ID
            session: 数据库会话
            status: 筛选状态（可选）
        """
        stmt = select(RefundApplication).where(
            RefundApplication.user_id == user_id
        )

        if status:
            stmt = stmt.where(RefundApplication.status == status)

        stmt = stmt.order_by(RefundApplication.created_at.desc())  # type: ignore

        result = await session.exec(stmt)
        return list(result. all())

    @staticmethod
    async def get_refund_by_id(
        refund_id: int,
        user_id: int,
        session: AsyncSession
    ) -> RefundApplication | None:
        """
        根据ID查询退货申请（带权限校验）
        """
        stmt = select(RefundApplication).where(
            RefundApplication.id == refund_id,
            RefundApplication.user_id == user_id  # 🔒 只能查自己的
        )
        result = await session.exec(stmt)
        return result.first()


# ==========================================
# 退货审核服务（管理员功能，v3.0 暂不实现）
# ==========================================

class RefundReviewService:
    """退货审核服务（预留）"""

    @staticmethod
    async def approve_refund(
        refund_id: int,
        admin_id: int,
        admin_note: str,
        session: AsyncSession
    ) -> tuple[bool, str]:
        """批准退货申请"""
        # TODO: v4.0 实现管理后台时添加
        return False, "Not implemented"

    @staticmethod
    async def reject_refund(
        refund_id: int,
        admin_id: int,
        admin_note: str,
        session: AsyncSession
    ) -> tuple[bool, str]:
        """拒绝退货申请"""
        # TODO: v4.0 实现
        return False, "Not implemented"
