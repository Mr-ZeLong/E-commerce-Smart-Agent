import pytest

from app.agents.account import AccountAgent
from app.models.state import make_agent_state
from tests._agents import DeterministicToolRegistry


@pytest.mark.asyncio
async def test_process_formats_account_response(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={
            "account": {
                "output": {
                    "username": "alice",
                    "email": "alice@example.com",
                    "full_name": "Alice Wang",
                    "phone": "13800138001",
                    "membership_level": "金卡",
                    "account_balance": 256.75,
                    "coupons": [
                        {"name": "满100减10", "expiry": "2025-12-31"},
                        {"name": "免运费券", "expiry": "2025-11-30"},
                    ],
                }
            }
        }
    )

    agent = AccountAgent(tool_registry=registry, llm=deterministic_llm)
    state = make_agent_state(question="查询我的账户", user_id=1)
    result = await agent.process(state)

    assert "Alice Wang" in result["response"]
    assert "金卡" in result["response"]
    assert "¥256.75" in result["response"]
    assert "满100减10" in result["response"]
    assert result["updated_state"]["account_data"]["username"] == "alice"


@pytest.mark.asyncio
async def test_process_handles_tool_error(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={"account": {"output": {"error": "未找到用户 ID 999 的账户信息。"}}}
    )

    agent = AccountAgent(tool_registry=registry, llm=deterministic_llm)
    state = make_agent_state(question="查询账户", user_id=999)
    result = await agent.process(state)

    assert "未找到用户" in result["response"]
    assert result["updated_state"]["account_data"] is None


@pytest.mark.asyncio
async def test_process_handles_no_coupons(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={
            "account": {
                "output": {
                    "username": "bob",
                    "email": "bob@example.com",
                    "full_name": "",
                    "phone": None,
                    "membership_level": "普通会员",
                    "account_balance": 0.0,
                    "coupons": [],
                }
            }
        }
    )

    agent = AccountAgent(tool_registry=registry, llm=deterministic_llm)
    state = make_agent_state(question="我的账户", user_id=3)
    result = await agent.process(state)

    assert "bob" in result["response"]
    assert "普通会员" in result["response"]
    assert "暂无可用优惠券" in result["response"]
