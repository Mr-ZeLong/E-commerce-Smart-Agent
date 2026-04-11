from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.order import OrderStatus
from app.models.refund import RefundReason, RefundStatus
from app.services.refund_service import (
    RefundApplicationService,
    RefundEligibilityChecker,
    process_refund_for_order,
)


@pytest.mark.asyncio
async def test_check_eligibility_pass():
    """通过所有规则的情况"""
    mock_order = MagicMock()
    mock_order.status = OrderStatus.DELIVERED
    mock_order.created_at = datetime.now(UTC) - timedelta(days=1)
    mock_order.items = []
    mock_session = AsyncMock()

    with patch.object(
        RefundEligibilityChecker,
        "_check_existing_refund",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result, msg = await RefundEligibilityChecker.check_eligibility(mock_order, mock_session)
        assert result is True
        assert msg == "订单符合退货条件"


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_order_status():
    """订单状态不在 ALLOWED_ORDER_STATUSES 时拒绝"""
    mock_order = MagicMock()
    mock_order.status = OrderStatus.PENDING
    mock_order.created_at = datetime.now(UTC)
    mock_order.items = []
    mock_session = AsyncMock()

    result, msg = await RefundEligibilityChecker.check_eligibility(mock_order, mock_session)
    assert result is False
    assert "订单状态为" in msg and "PENDING" in msg


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_existing_refund():
    """已有进行中的退款申请时拒绝"""
    mock_order = MagicMock()
    mock_order.status = OrderStatus.DELIVERED
    mock_order.created_at = datetime.now(UTC) - timedelta(days=1)
    mock_order.items = []
    mock_session = AsyncMock()

    existing_refund = MagicMock()
    existing_refund.status = RefundStatus.PENDING

    with patch.object(
        RefundEligibilityChecker,
        "_check_existing_refund",
        new_callable=AsyncMock,
        return_value=existing_refund,
    ):
        result, msg = await RefundEligibilityChecker.check_eligibility(mock_order, mock_session)
        assert result is False
        assert "已存在退货申请" in msg


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_time_limit():
    """超过 7 天退货期限时拒绝"""
    mock_order = MagicMock()
    mock_order.status = OrderStatus.DELIVERED
    mock_order.created_at = datetime.now(UTC) - timedelta(days=10)
    mock_order.items = []
    mock_session = AsyncMock()

    with patch.object(
        RefundEligibilityChecker,
        "_check_existing_refund",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result, msg = await RefundEligibilityChecker.check_eligibility(mock_order, mock_session)
        assert result is False
        assert "已超过退货期限" in msg


@pytest.mark.asyncio
async def test_check_eligibility_reject_by_category():
    """包含不可退货商品时拒绝"""
    mock_order = MagicMock()
    mock_order.status = OrderStatus.DELIVERED
    mock_order.created_at = datetime.now(UTC) - timedelta(days=1)
    mock_order.items = [{"name": "进口食品大礼包"}]
    mock_session = AsyncMock()

    with patch.object(
        RefundEligibilityChecker,
        "_check_existing_refund",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result, msg = await RefundEligibilityChecker.check_eligibility(mock_order, mock_session)
        assert result is False
        assert "包含不可退货商品" in msg


@pytest.mark.asyncio
async def test_create_refund_application_success():
    """成功创建退款申请"""
    mock_order = MagicMock()
    mock_order.id = 1
    mock_order.total_amount = 99.9

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_order)))

    with patch.object(
        RefundEligibilityChecker,
        "check_eligibility",
        new_callable=AsyncMock,
        return_value=(True, "订单符合退货条件"),
    ):
        success, msg, refund_app = await RefundApplicationService.create_refund_application(
            order_id=1,
            user_id=100,
            reason_detail="不想要了",
            reason_category=RefundReason.CHANGED_MIND,
            session=mock_session,
        )
        assert success is True
        assert "退货申请已提交" in msg
        assert refund_app is not None
        assert refund_app.status == RefundStatus.PENDING
        assert refund_app.refund_amount == 99.9
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_refund_application_order_not_found():
    """订单不存在时返回失败"""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))

    success, msg, refund_app = await RefundApplicationService.create_refund_application(
        order_id=999,
        user_id=100,
        reason_detail="质量问题",
        reason_category=RefundReason.QUALITY_ISSUE,
        session=mock_session,
    )
    assert success is False
    assert "订单不存在或无权访问" in msg
    assert refund_app is None


@pytest.mark.asyncio
async def test_create_refund_application_not_eligible():
    """资格校验失败时返回失败"""
    mock_order = MagicMock()
    mock_order.id = 1

    mock_session = AsyncMock()
    mock_session.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_order)))

    with patch.object(
        RefundEligibilityChecker,
        "check_eligibility",
        new_callable=AsyncMock,
        return_value=(False, "订单已超过退货期限"),
    ):
        success, msg, refund_app = await RefundApplicationService.create_refund_application(
            order_id=1,
            user_id=100,
            reason_detail="质量问题",
            reason_category=RefundReason.QUALITY_ISSUE,
            session=mock_session,
        )
        assert success is False
        assert "退货申请被拒绝" in msg
        assert "订单已超过退货期限" in msg
        assert refund_app is None


@pytest.mark.asyncio
async def test_process_refund_for_order_success():
    """成功处理退款申请"""
    mock_order = MagicMock()
    mock_order.id = 42
    mock_order.order_sn = "ORD2024001"
    mock_order.total_amount = 199.0

    mock_refund = MagicMock()
    mock_refund.id = 7
    mock_refund.refund_amount = 199.0
    mock_refund.status = RefundStatus.PENDING
    mock_refund.reason_detail = "不喜欢"

    with (
        patch(
            "app.services.refund_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
        patch.object(
            RefundEligibilityChecker,
            "check_eligibility",
            new_callable=AsyncMock,
            return_value=(True, "订单符合退货条件"),
        ),
        patch.object(
            RefundApplicationService,
            "create_refund_application",
            new_callable=AsyncMock,
            return_value=(True, "申请已提交", mock_refund),
        ),
    ):
        success, msg, data = await process_refund_for_order(
            order_sn="ORD2024001",
            user_id=100,
            reason_detail="不喜欢",
            reason_category=RefundReason.CHANGED_MIND,
            session=AsyncMock(),
        )
        assert success is True
        assert data is not None
        assert data["refund_id"] == 7
        assert data["amount"] == 199.0
        assert data["status"] == RefundStatus.PENDING
        assert data["reason_detail"] == "不喜欢"


@pytest.mark.asyncio
async def test_process_refund_for_order_not_found():
    """订单不存在时失败"""
    with patch(
        "app.services.refund_service.get_order_by_sn",
        new_callable=AsyncMock,
        return_value=None,
    ):
        success, msg, data = await process_refund_for_order(
            order_sn="ORD999",
            user_id=100,
            reason_detail="不喜欢",
            reason_category=RefundReason.CHANGED_MIND,
            session=AsyncMock(),
        )
        assert success is False
        assert "未找到订单" in msg
        assert data is None


@pytest.mark.asyncio
async def test_process_refund_for_order_not_eligible():
    """资格校验失败时返回失败"""
    mock_order = MagicMock()
    mock_order.id = 42
    mock_order.order_sn = "ORD2024001"

    with (
        patch(
            "app.services.refund_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
        patch.object(
            RefundEligibilityChecker,
            "check_eligibility",
            new_callable=AsyncMock,
            return_value=(False, "订单已超过退货期限"),
        ),
    ):
        success, msg, data = await process_refund_for_order(
            order_sn="ORD2024001",
            user_id=100,
            reason_detail="不喜欢",
            reason_category=RefundReason.CHANGED_MIND,
            session=AsyncMock(),
        )
        assert success is False
        assert "不符合退货条件" in msg
        assert "订单已超过退货期限" in msg
        assert data is None


@pytest.mark.asyncio
async def test_create_refund_application_flush_exception():
    """数据库 flush 抛异常时返回失败"""
    mock_order = MagicMock()
    mock_order.id = 1
    mock_order.total_amount = 99.9

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_order)))
    mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("DB connection lost"))

    with patch.object(
        RefundEligibilityChecker,
        "check_eligibility",
        new_callable=AsyncMock,
        return_value=(True, "订单符合退货条件"),
    ):
        success, msg, refund_app = await RefundApplicationService.create_refund_application(
            order_id=1,
            user_id=100,
            reason_detail="不想要了",
            reason_category=RefundReason.CHANGED_MIND,
            session=mock_session,
        )
        assert success is False
        assert "提交失败" in msg
        assert "DB connection lost" in msg
        assert refund_app is None
