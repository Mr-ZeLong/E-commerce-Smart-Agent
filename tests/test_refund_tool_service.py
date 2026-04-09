from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.order import Order, OrderStatus
from app.models.refund import RefundStatus
from app.services import refund_tool_service


@pytest.mark.asyncio
async def test_check_refund_eligibility_eligible():
    """订单符合退货条件"""
    mock_order = MagicMock(spec=Order)
    mock_order.items = [{"name": "T恤"}, {"name": "裤子"}]
    mock_order.total_amount = 199.0
    mock_order.status = OrderStatus.DELIVERED

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.refund_tool_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.refund_tool_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
        patch(
            "app.services.refund_tool_service.RefundEligibilityChecker.check_eligibility",
            new_callable=AsyncMock,
            return_value=(True, "订单符合退货条件"),
        ),
    ):
        result = await refund_tool_service.check_refund_eligibility("SN20240001", 1)

    assert "✅" in result
    assert "符合退货条件" in result
    assert "T恤" in result
    assert "199.0" in result


@pytest.mark.asyncio
async def test_check_refund_eligibility_not_eligible():
    """订单不符合退货条件"""
    mock_order = MagicMock(spec=Order)
    mock_order.items = [{"name": "T恤"}]
    mock_order.total_amount = 199.0
    mock_order.status = OrderStatus.PENDING

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.refund_tool_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.refund_tool_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
        patch(
            "app.services.refund_tool_service.RefundEligibilityChecker.check_eligibility",
            new_callable=AsyncMock,
            return_value=(False, "订单状态为 PENDING，只有已发货或已签收的订单才能退货"),
        ),
    ):
        result = await refund_tool_service.check_refund_eligibility("SN20240001", 1)

    assert "❌" in result
    assert "不符合退货条件" in result
    assert "PENDING" in result


@pytest.mark.asyncio
async def test_submit_refund_application_success():
    """提交退货申请成功"""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.refund_tool_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.refund_tool_service.process_refund_for_order",
            new_callable=AsyncMock,
            return_value=(
                True,
                "退货申请已提交（申请编号：7），等待审核",
                {"refund_id": 7, "amount": 199.0, "status": RefundStatus.PENDING, "reason_detail": "质量问题"},
            ),
        ),
    ):
        result = await refund_tool_service.submit_refund_application(
            "SN20240001", 1, "商品有破损", "QUALITY_ISSUE"
        )

    assert "✅" in result
    assert "退货申请提交成功" in result
    assert "#7" in result
    assert "SN20240001" in result


@pytest.mark.asyncio
async def test_submit_refund_application_failure():
    """提交退货申请失败"""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.refund_tool_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.refund_tool_service.process_refund_for_order",
            new_callable=AsyncMock,
            return_value=(False, "该订单不符合退货条件：已超过退货期限", None),
        ),
    ):
        result = await refund_tool_service.submit_refund_application(
            "SN20240001", 1, "不想要了"
        )

    assert "❌" in result
    assert "退货申请失败" in result
    assert "已超过退货期限" in result


@pytest.mark.asyncio
async def test_query_refund_status_by_id():
    """按 refund_id 查询退货状态"""
    mock_refund = MagicMock()
    mock_refund.id = 7
    mock_refund.order_id = 42
    mock_refund.status = RefundStatus.PENDING
    mock_refund.refund_amount = 199.0
    mock_refund.created_at = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
    mock_refund.reason_detail = "质量问题"
    mock_refund.reviewed_at = None
    mock_refund.admin_note = None

    mock_order = MagicMock(spec=Order)
    mock_order.order_sn = "SN20240001"
    mock_order.items = [{"name": "T恤"}]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.first.return_value = mock_order
    mock_session.exec = AsyncMock(return_value=mock_result)

    with (
        patch(
            "app.services.refund_tool_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.refund_tool_service.RefundApplicationService.get_refund_by_id",
            new_callable=AsyncMock,
            return_value=mock_refund,
        ),
    ):
        result = await refund_tool_service.query_refund_status(user_id=1, refund_id=7)

    assert "📋 退货申请详情（#7）" in result
    assert "SN20240001" in result
    assert "PENDING" in result
    assert "199.0" in result
    assert "审核中" in result


@pytest.mark.asyncio
async def test_query_refund_status_list_all():
    """查询用户全部退货申请"""
    mock_refund_1 = MagicMock()
    mock_refund_1.id = 1
    mock_refund_1.order_id = 10
    mock_refund_1.status = RefundStatus.PENDING
    mock_refund_1.refund_amount = 99.0
    mock_refund_1.created_at = datetime(2024, 1, 10, 10, 0, tzinfo=UTC)

    mock_refund_2 = MagicMock()
    mock_refund_2.id = 2
    mock_refund_2.order_id = 20
    mock_refund_2.status = RefundStatus.APPROVED
    mock_refund_2.refund_amount = 199.0
    mock_refund_2.created_at = datetime(2024, 1, 12, 14, 0, tzinfo=UTC)

    mock_order_1 = MagicMock(spec=Order)
    mock_order_1.order_sn = "SN20240001"

    mock_order_2 = MagicMock(spec=Order)
    mock_order_2.order_sn = "SN20240002"

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    exec_results = [
        MagicMock(first=MagicMock(return_value=mock_order_1)),
        MagicMock(first=MagicMock(return_value=mock_order_2)),
    ]
    mock_session.exec = AsyncMock(side_effect=exec_results)

    with (
        patch(
            "app.services.refund_tool_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.refund_tool_service.RefundApplicationService.get_user_refund_applications",
            new_callable=AsyncMock,
            return_value=[mock_refund_1, mock_refund_2],
        ),
    ):
        result = await refund_tool_service.query_refund_status(user_id=1)

    assert "共 2 条" in result
    assert "申请 #1" in result
    assert "申请 #2" in result
    assert "SN20240001" in result
    assert "SN20240002" in result
    assert "⏳" in result  # PENDING
    assert "✅" in result  # APPROVED
