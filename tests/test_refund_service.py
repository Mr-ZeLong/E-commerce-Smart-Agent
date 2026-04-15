from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundReason, RefundStatus
from app.models.user import User
from app.services.refund_service import (
    RefundApplicationService,
    RefundEligibilityChecker,
    process_refund_for_order,
)


async def _create_test_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name="Test User",
        password_hash=User.hash_password("testpass"),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_test_order(
    session,
    user_id: int,
    order_sn: str,
    status: OrderStatus = OrderStatus.DELIVERED,
    total_amount: Decimal = Decimal("199.0"),
    created_at: datetime | None = None,
    items: list | None = None,
) -> Order:
    order = Order(
        order_sn=order_sn,
        user_id=user_id,
        status=status,
        total_amount=total_amount,
        shipping_address="Test Address",
        created_at=created_at or datetime.now(UTC),
        items=items if items is not None else [],
    )
    session.add(order)
    await session.flush()
    await session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_check_eligibility_pass(db_session):
    """通过所有规则的情况"""
    user = await _create_test_user(db_session, "elig_user_pass")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240001",
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    result, msg = await RefundEligibilityChecker.check_eligibility(order, db_session)
    assert result is True
    assert msg == "订单符合退货条件"


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_order_status(db_session):
    """订单状态不在 ALLOWED_ORDER_STATUSES 时拒绝"""
    user = await _create_test_user(db_session, "elig_user_status")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240002",
        status=OrderStatus.PENDING,
    )
    result, msg = await RefundEligibilityChecker.check_eligibility(order, db_session)
    assert result is False
    assert "订单状态为" in msg and "PENDING" in msg


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_existing_refund(db_session):
    """已有进行中的退款申请时拒绝"""
    user = await _create_test_user(db_session, "elig_user_existing")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240003",
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert order.id is not None
    existing = RefundApplication(
        order_id=order.id,
        user_id=user.id,
        status=RefundStatus.PENDING,
        reason_detail="现有申请",
        reason_category=RefundReason.OTHER,
        refund_amount=order.total_amount,
    )
    db_session.add(existing)
    await db_session.flush()

    result, msg = await RefundEligibilityChecker.check_eligibility(order, db_session)
    assert result is False
    assert "已存在退货申请" in msg


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_time_limit(db_session):
    """超过 7 天退货期限时拒绝"""
    user = await _create_test_user(db_session, "elig_user_time")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240004",
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    result, msg = await RefundEligibilityChecker.check_eligibility(order, db_session)
    assert result is False
    assert "已超过退货期限" in msg


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_category(db_session):
    """包含不可退货商品时拒绝"""
    user = await _create_test_user(db_session, "elig_user_cat")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240005",
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC) - timedelta(days=1),
        items=[{"name": "进口食品大礼包"}],
    )
    result, msg = await RefundEligibilityChecker.check_eligibility(order, db_session)
    assert result is False
    assert "包含不可退货商品" in msg


@pytest.mark.asyncio
async def test_create_refund_application_success(db_session):
    """成功创建退款申请"""
    user = await _create_test_user(db_session, "refund_app_user")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240006",
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert order.id is not None
    success, msg, refund_app = await RefundApplicationService.create_refund_application(
        order_id=order.id,
        user_id=user.id,
        reason_detail="不想要了",
        reason_category=RefundReason.CHANGED_MIND,
        session=db_session,
    )
    assert success is True
    assert "退货申请已提交" in msg
    assert refund_app is not None
    assert refund_app.status == RefundStatus.PENDING
    assert refund_app.refund_amount == 199.0


@pytest.mark.asyncio
async def test_create_refund_application_order_not_found(db_session):
    """订单不存在时返回失败"""
    success, msg, refund_app = await RefundApplicationService.create_refund_application(
        order_id=99999,
        user_id=1,
        reason_detail="质量问题",
        reason_category=RefundReason.QUALITY_ISSUE,
        session=db_session,
    )
    assert success is False
    assert "订单不存在或无权访问" in msg
    assert refund_app is None


@pytest.mark.asyncio
async def test_create_refund_application_not_eligible(db_session):
    """资格校验失败时返回失败"""
    user = await _create_test_user(db_session, "refund_app_inelig")
    assert user.id is not None
    order = await _create_test_order(
        db_session,
        user.id,
        "SN20240007",
        status=OrderStatus.PENDING,
    )
    order_id = order.id
    assert order_id is not None
    success, msg, refund_app = await RefundApplicationService.create_refund_application(
        order_id=order_id,
        user_id=user.id,
        reason_detail="质量问题",
        reason_category=RefundReason.QUALITY_ISSUE,
        session=db_session,
    )
    assert success is False
    assert "退货申请被拒绝" in msg
    assert "订单状态为" in msg
    assert refund_app is None


@pytest.mark.asyncio
async def test_process_refund_for_order_success(db_session):
    """成功处理退款申请"""
    user = await _create_test_user(db_session, "proc_refund_user")
    assert user.id is not None
    _order = await _create_test_order(
        db_session,
        user.id,
        "ORD2024001",
        status=OrderStatus.DELIVERED,
        created_at=datetime.now(UTC) - timedelta(days=1),
        total_amount=Decimal("199.0"),
    )
    success, _msg, data, refund_app = await process_refund_for_order(
        order_sn="ORD2024001",
        user_id=user.id,
        reason_detail="不喜欢",
        reason_category=RefundReason.CHANGED_MIND,
        session=db_session,
    )
    assert success is True
    assert data is not None
    assert data["refund_id"] is not None
    assert data["amount"] == 199.0
    assert data["status"] == RefundStatus.PENDING
    assert data["reason_detail"] == "不喜欢"
    assert refund_app is not None


@pytest.mark.asyncio
async def test_process_refund_for_order_not_found(db_session):
    """订单不存在时失败"""
    success, msg, data, refund_app = await process_refund_for_order(
        order_sn="ORD999",
        user_id=1,
        reason_detail="不喜欢",
        reason_category=RefundReason.CHANGED_MIND,
        session=db_session,
    )
    assert success is False
    assert "未找到订单" in msg
    assert data is None
    assert refund_app is None


@pytest.mark.asyncio
async def test_process_refund_for_order_not_eligible(db_session):
    """资格校验失败时返回失败"""
    user = await _create_test_user(db_session, "proc_refund_inelig")
    assert user.id is not None
    _order = await _create_test_order(
        db_session,
        user.id,
        "ORD2024002",
        status=OrderStatus.PENDING,
    )
    success, msg, data, refund_app = await process_refund_for_order(
        order_sn="ORD2024002",
        user_id=user.id,
        reason_detail="不喜欢",
        reason_category=RefundReason.CHANGED_MIND,
        session=db_session,
    )
    assert success is False
    assert "不符合退货条件" in msg
    assert data is None
    assert refund_app is None


@pytest.mark.asyncio
async def test_create_refund_application_flush_exception(db_session):
    """数据库 flush 抛异常时返回失败。

    选择方案 b)：传入 order 对象绕过前置查询，同时使用一个不存在的 user_id，
    使 RefundApplication 在 flush 时因外键约束失败而触发真实的 SQLAlchemyError，
    从而覆盖异常处理分支。
    """
    user = await _create_test_user(db_session, "flush_err_user")
    assert user.id is not None
    order = await _create_test_order(db_session, user.id, "SN20240008")
    order_id = order.id
    assert order_id is not None

    success, msg, refund_app = await RefundApplicationService.create_refund_application(
        order_id=order_id,
        user_id=99999,
        reason_detail="不想要了",
        reason_category=RefundReason.CHANGED_MIND,
        session=db_session,
        order=order,
    )
    assert success is False
    assert "提交失败" in msg
    assert refund_app is None
