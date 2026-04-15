import pytest

from app.agents.payment import PaymentAgent
from app.models.state import make_agent_state
from tests._agents import DeterministicToolRegistry


@pytest.fixture
def payment_agent(deterministic_llm):
    registry = DeterministicToolRegistry()
    agent = PaymentAgent(tool_registry=registry, llm=deterministic_llm)
    return agent, registry


@pytest.mark.asyncio
async def test_payment_agent_process_with_records(payment_agent):
    """有支付/退款记录时返回格式化回复"""
    agent, registry = payment_agent
    registry.responses = {
        "payment": {
            "output": {
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
        }
    }

    state = make_agent_state(question="查询支付状态", user_id=1)
    result = await agent.process(state)

    assert "已支付" in result["response"]
    assert "已开票" in result["response"]
    assert "SN20240001" in result["response"]
    assert result["updated_state"]["payment_data"] == registry.responses["payment"]["output"]


@pytest.mark.asyncio
async def test_payment_agent_process_empty_records(payment_agent):
    """无记录时返回友好空状态提示"""
    agent, registry = payment_agent
    registry.responses = {
        "payment": {
            "output": {
                "payment_status": "未知",
                "invoice_status": "未查询到发票信息",
                "refund_records": [],
                "message": "未查询到相关支付/退款记录",
            }
        }
    }

    state = make_agent_state(question="查询退款记录", user_id=1)
    result = await agent.process(state)

    assert "未查询到" in result["response"]
    assert result["updated_state"]["payment_data"] == registry.responses["payment"]["output"]
