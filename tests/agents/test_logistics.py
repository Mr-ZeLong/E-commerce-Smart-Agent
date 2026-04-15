import pytest

from app.agents.logistics import LogisticsAgent
from app.models.state import make_agent_state
from tests._agents import DeterministicToolRegistry


@pytest.fixture
def agent(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={
            "logistics": {
                "output": {
                    "tracking_number": "SF1234567890",
                    "carrier": "顺丰速运",
                    "status": "运输中",
                    "latest_update": "快件已到达【北京顺义集散中心】",
                    "estimated_delivery": "2024-01-20",
                }
            }
        }
    )
    return LogisticsAgent(tool_registry=registry, llm=deterministic_llm)


@pytest.fixture
def agent_not_found(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={"logistics": {"output": {"status": "未找到订单"}}}
    )
    return LogisticsAgent(tool_registry=registry, llm=deterministic_llm)


@pytest.mark.asyncio
async def test_logistics_agent_happy_path(agent):
    state = make_agent_state(
        question="我的快递到哪了？", user_id=1, slots={"order_sn": "SN20240001"}
    )
    result = await agent.process(state)

    assert "物流单号: SF1234567890" in result["response"]
    assert "运输中" in result["response"]
    assert "顺丰速运" in result["response"]
    assert result["updated_state"]["order_data"]["status"] == "运输中"


@pytest.mark.asyncio
async def test_logistics_agent_not_found(agent_not_found):
    state = make_agent_state(
        question="我的快递到哪了？", user_id=1, slots={"order_sn": "SN99999999"}
    )
    result = await agent_not_found.process(state)

    assert "抱歉" in result["response"]
    assert "未找到" in result["response"]
    assert result["updated_state"]["order_data"]["status"] == "未找到订单"
