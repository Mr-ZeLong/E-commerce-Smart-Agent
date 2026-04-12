from unittest.mock import AsyncMock

import pytest

from app.agents.cart import CartAgent
from app.models.state import make_agent_state


@pytest.fixture
def agent():
    registry = AsyncMock()
    registry.execute.return_value = AsyncMock()
    registry.execute.return_value.output = {
        "action": "QUERY",
        "items": [
            {"name": "T恤", "quantity": 2, "price": 99.0, "subtotal": 198.0},
        ],
        "total": 198.0,
    }
    return CartAgent(tool_registry=registry, llm=AsyncMock())


@pytest.mark.asyncio
async def test_cart_agent_query(agent):
    state = make_agent_state(question="购物车里有啥")
    result = await agent.process(state)
    assert "T恤" in result["response"]
    assert "198.0" in result["response"]
    assert result["updated_state"]["cart_data"]["action"] == "QUERY"


@pytest.mark.asyncio
async def test_cart_agent_empty():
    registry = AsyncMock()
    registry.execute.return_value = AsyncMock()
    registry.execute.return_value.output = {"action": "QUERY", "items": [], "total": 0.0}
    agent = CartAgent(tool_registry=registry, llm=AsyncMock())

    state = make_agent_state(question="我的购物车")
    result = await agent.process(state)
    assert "空的" in result["response"]


@pytest.mark.asyncio
async def test_cart_agent_add():
    registry = AsyncMock()
    registry.execute.return_value = AsyncMock()
    registry.execute.return_value.output = {
        "action": "ADD",
        "name": "运动鞋",
        "quantity": 1,
        "items": [{"name": "运动鞋", "quantity": 1, "subtotal": 399.0}],
        "total": 399.0,
    }
    agent = CartAgent(tool_registry=registry, llm=AsyncMock())

    state = make_agent_state(question="加一双运动鞋")
    result = await agent.process(state)
    assert "运动鞋" in result["response"]
    assert "加入购物车" in result["response"]


@pytest.mark.asyncio
async def test_cart_agent_remove():
    registry = AsyncMock()
    registry.execute.return_value = AsyncMock()
    registry.execute.return_value.output = {
        "action": "REMOVE",
        "name": "T恤",
        "items": [],
        "total": 0.0,
    }
    agent = CartAgent(tool_registry=registry, llm=AsyncMock())

    state = make_agent_state(question="把T恤删掉")
    result = await agent.process(state)
    assert "已移除" in result["response"]


@pytest.mark.asyncio
async def test_cart_agent_error():
    registry = AsyncMock()
    registry.execute.return_value = AsyncMock()
    registry.execute.return_value.output = {
        "status": "error",
        "reason": "商品库存不足",
    }
    agent = CartAgent(tool_registry=registry, llm=AsyncMock())

    state = make_agent_state(question="加一件缺货商品")
    result = await agent.process(state)
    assert "操作失败" in result["response"]
    assert "库存不足" in result["response"]
