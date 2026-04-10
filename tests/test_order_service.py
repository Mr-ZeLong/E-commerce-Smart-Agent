from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentResult
from app.models.order import Order, OrderStatus
from app.models.refund import RefundStatus
from app.services.order_service import OrderService


@pytest.fixture
def order_service() -> OrderService:
    return OrderService()


@pytest.mark.asyncio
async def test_get_order_for_user_with_order_sn(order_service: OrderService):
    """通过订单号查询订单"""
    mock_order = MagicMock(spec=Order)
    mock_order.model_dump.return_value = {
        "order_sn": "SN20240001",
        "status": OrderStatus.SHIPPED,
        "total_amount": 199.0,
    }

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.order_service.async_session_maker",
            return_value=mock_session,
        ) as mock_maker,
        patch(
            "app.services.order_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
    ):
        result = await order_service.get_order_for_user("SN20240001", 1)

    mock_maker.assert_called_once()
    assert result == {
        "order_sn": "SN20240001",
        "status": OrderStatus.SHIPPED,
        "total_amount": 199.0,
    }


@pytest.mark.asyncio
async def test_get_order_for_user_without_order_sn(order_service: OrderService):
    """不传入订单号时返回用户最新订单"""
    mock_order = MagicMock(spec=Order)
    mock_order.model_dump.return_value = {
        "order_sn": "SN20240002",
        "status": OrderStatus.DELIVERED,
        "total_amount": 299.0,
    }

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.first.return_value = mock_order
    mock_session.exec = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.order_service.async_session_maker",
        return_value=mock_session,
    ) as mock_maker:
        result = await order_service.get_order_for_user(None, 1)

    mock_maker.assert_called_once()
    mock_session.exec.assert_awaited_once()
    assert result == {
        "order_sn": "SN20240002",
        "status": OrderStatus.DELIVERED,
        "total_amount": 299.0,
    }


@pytest.mark.asyncio
async def test_handle_refund_request_success(order_service: OrderService):
    """退款申请成功路径"""
    mock_order = MagicMock(spec=Order)
    mock_order.id = 42
    mock_order.model_dump.return_value = {"order_sn": "SN20240001", "status": OrderStatus.DELIVERED}

    mock_refund_app = MagicMock()
    mock_refund_app.id = 7

    mock_audit = MagicMock()
    mock_audit.id = 100

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    refund_result_mock = MagicMock()
    refund_result_mock.one_or_none.return_value = mock_refund_app
    mock_session.exec = AsyncMock(return_value=refund_result_mock)

    with (
        patch(
            "app.services.order_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.order_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
        patch(
            "app.services.order_service.process_refund_for_order",
            new_callable=AsyncMock,
            return_value=(
                True,
                "退货申请已提交（申请编号：7），等待审核",
                {
                    "refund_id": 7,
                    "amount": 199.0,
                    "status": RefundStatus.PENDING,
                    "reason_detail": "质量问题",
                },
            ),
        ),
        patch(
            "app.services.order_service.RefundRiskService.assess_and_create_audit",
            new_callable=AsyncMock,
            return_value=mock_audit,
        ) as mock_assess,
        patch(
            "app.services.order_service.notify_admin_audit",
        ) as mock_notify,
    ):
        result = await order_service.handle_refund_request(
            "我要退货，订单号 SN20240001，质量问题",
            user_id=1,
            thread_id="thread-1",
        )

    assert isinstance(result, AgentResult)
    assert "✅" in result.response
    assert result.updated_state["refund_flow_active"] is True
    assert result.updated_state["order_data"]["order_sn"] == "SN20240001"
    assert result.updated_state["refund_data"]["refund_id"] == 7
    mock_session.commit.assert_awaited_once()
    mock_assess.assert_awaited_once()
    mock_notify.delay.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_handle_refund_request_missing_order_sn(order_service: OrderService):
    """未提供订单号时返回提示"""
    result = await order_service.handle_refund_request("我要退货", user_id=1)

    assert isinstance(result, AgentResult)
    assert "请提供订单号" in result.response
    assert result.updated_state["refund_flow_active"] is False


@pytest.mark.asyncio
async def test_handle_refund_request_order_not_found(order_service: OrderService):
    """订单不存在时返回错误"""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.order_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.order_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await order_service.handle_refund_request(
            "我要退货，订单号 SN99999999",
            user_id=1,
        )

    assert isinstance(result, AgentResult)
    assert "未找到订单" in result.response
    assert result.updated_state["refund_flow_active"] is False


@pytest.mark.asyncio
async def test_handle_refund_request_order_id_none(order_service: OrderService):
    """订单 id 为 None 时返回数据异常提示"""
    mock_order = MagicMock(spec=Order)
    mock_order.id = None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.order_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.order_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
    ):
        result = await order_service.handle_refund_request(
            "我要退货，订单号 SN20240001",
            user_id=1,
        )

    assert isinstance(result, AgentResult)
    assert "订单数据异常" in result.response
    assert result.updated_state["refund_flow_active"] is False


@pytest.mark.asyncio
async def test_handle_refund_request_refund_failed(order_service: OrderService):
    """process_refund_for_order 返回失败时返回错误消息"""
    mock_order = MagicMock(spec=Order)
    mock_order.id = 42
    mock_order.model_dump.return_value = {
        "order_sn": "SN20240001",
        "status": OrderStatus.DELIVERED,
    }

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.order_service.async_session_maker",
            return_value=mock_session,
        ),
        patch(
            "app.services.order_service.get_order_by_sn",
            new_callable=AsyncMock,
            return_value=mock_order,
        ),
        patch(
            "app.services.order_service.process_refund_for_order",
            new_callable=AsyncMock,
            return_value=(False, "超期", None),
        ),
    ):
        result = await order_service.handle_refund_request(
            "我要退货，订单号 SN20240001",
            user_id=1,
        )

    assert isinstance(result, AgentResult)
    assert "超期" in result.response
    assert result.updated_state["refund_flow_active"] is False
    assert result.updated_state["order_data"]["order_sn"] == "SN20240001"
