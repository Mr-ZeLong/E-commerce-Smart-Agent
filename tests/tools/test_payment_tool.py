from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundStatus
from app.models.state import make_agent_state
from app.tools.payment_tool import PaymentTool


@pytest.fixture
def payment_tool() -> PaymentTool:
    return PaymentTool()


@pytest.mark.asyncio
async def test_payment_tool_with_order_sn(payment_tool: PaymentTool):
    """提供订单号时查询订单和退款记录"""
    mock_order = MagicMock(spec=Order)
    mock_order.order_sn = "SN20240001"
    mock_order.status = OrderStatus.PAID
    mock_order.total_amount = 199.0

    mock_refund = MagicMock(spec=RefundApplication)
    mock_refund.id = 1
    mock_refund.refund_amount = 199.0
    mock_refund.status = RefundStatus.PENDING
    mock_refund.created_at = datetime(2024, 1, 1, 12, 0, 0)
    mock_refund.order_sn = "SN20240001"

    # Mock session exec results: first for refund query, second for order query
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    refund_result = MagicMock()
    refund_result.all.return_value = [mock_refund]
    order_result = MagicMock()
    order_result.one_or_none.return_value = mock_order

    def exec_side_effect(stmt):
        # Determine which query based on model type in statement
        if "RefundApplication" in str(stmt) or "refund_applications" in str(stmt):
            return refund_result
        return order_result

    mock_session.exec = AsyncMock(side_effect=exec_side_effect)

    with patch(
        "app.tools.payment_tool.async_session_maker",
        return_value=mock_session,
    ):
        state = make_agent_state(
            question="查询支付状态 SN20240001",
            user_id=1,
            slots={"order_sn": "SN20240001"},
        )
        result = await payment_tool.execute(state)

    assert result.output["payment_status"] == "已支付"
    assert result.output["invoice_status"] == "已开票"
    assert len(result.output["refund_records"]) == 1
    assert result.output["refund_records"][0]["refund_id"] == 1
    assert result.output["refund_records"][0]["amount"] == 199.0
    assert result.output["refund_records"][0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_payment_tool_without_order_sn(payment_tool: PaymentTool):
    """未提供订单号时仅查询退款记录"""
    mock_refund = MagicMock(spec=RefundApplication)
    mock_refund.id = 2
    mock_refund.refund_amount = 99.0
    mock_refund.status = RefundStatus.APPROVED
    mock_refund.created_at = datetime(2024, 1, 2, 12, 0, 0)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    refund_result = MagicMock()
    refund_result.all.return_value = [mock_refund]

    mock_session.exec = AsyncMock(return_value=refund_result)

    with patch(
        "app.tools.payment_tool.async_session_maker",
        return_value=mock_session,
    ):
        state = make_agent_state(
            question="查询我的退款记录",
            user_id=1,
        )
        result = await payment_tool.execute(state)

    assert result.output["payment_status"] == "未知"
    assert result.output["invoice_status"] == "未查询到发票信息"
    assert len(result.output["refund_records"]) == 1
    assert result.output["refund_records"][0]["refund_id"] == 2


@pytest.mark.asyncio
async def test_payment_tool_no_records(payment_tool: PaymentTool):
    """无任何记录时返回空状态"""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    refund_result = MagicMock()
    refund_result.all.return_value = []
    order_result = MagicMock()
    order_result.one_or_none.return_value = None

    def exec_side_effect(stmt):
        if "RefundApplication" in str(stmt) or "refund_applications" in str(stmt):
            return refund_result
        return order_result

    mock_session.exec = AsyncMock(side_effect=exec_side_effect)

    with patch(
        "app.tools.payment_tool.async_session_maker",
        return_value=mock_session,
    ):
        state = make_agent_state(
            question="查询支付状态 SN99999999",
            user_id=1,
            slots={"order_sn": "SN99999999"},
        )
        result = await payment_tool.execute(state)

    assert result.output["payment_status"] == "未知"
    assert result.output["invoice_status"] == "未查询到发票信息"
    assert result.output["refund_records"] == []
    assert result.output["message"] == "未查询到相关支付/退款记录"
