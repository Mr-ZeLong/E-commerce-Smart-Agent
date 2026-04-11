from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.payment import PaymentAgent
from app.models.state import make_agent_state
from app.tools.registry import ToolRegistry


@pytest.fixture
def payment_agent() -> PaymentAgent:
    registry = ToolRegistry()
    return PaymentAgent(tool_registry=registry, llm=MagicMock())


@pytest.mark.asyncio
async def test_payment_agent_process_with_records(payment_agent: PaymentAgent):
    """有支付/退款记录时返回格式化回复"""
    mock_tool_result = MagicMock()
    mock_tool_result.output = {
        "payment_status": "已支付",
        "invoice_status": "已开票",
        "refund_records": [
            {
                "refund_id": 1,
                "order_sn": "SN20240001",
                "amount": 199.0,
                "status": "PENDING",
                "created_at": "2024-01-01 12:00:00",
            }
        ],
    }

    with patch.object(
        payment_agent.tool_registry, "execute", new_callable=AsyncMock
    ) as mock_execute:
        mock_execute.return_value = mock_tool_result

        state = make_agent_state(question="查询支付状态", user_id=1)
        result = await payment_agent.process(state)

        mock_execute.assert_awaited_once_with("payment", state)
        assert "已支付" in result["response"]
        assert "已开票" in result["response"]
        assert "SN20240001" in result["response"]
        assert result["updated_state"]["payment_data"] == mock_tool_result.output


@pytest.mark.asyncio
async def test_payment_agent_process_empty_records(payment_agent: PaymentAgent):
    """无记录时返回友好空状态提示"""
    mock_tool_result = MagicMock()
    mock_tool_result.output = {
        "payment_status": "未知",
        "invoice_status": "未查询到发票信息",
        "refund_records": [],
        "message": "未查询到相关支付/退款记录",
    }

    with patch.object(
        payment_agent.tool_registry, "execute", new_callable=AsyncMock
    ) as mock_execute:
        mock_execute.return_value = mock_tool_result

        state = make_agent_state(question="查询退款记录", user_id=1)
        result = await payment_agent.process(state)

        mock_execute.assert_awaited_once_with("payment", state)
        assert "未查询到" in result["response"]
        assert result["updated_state"]["payment_data"] == mock_tool_result.output
