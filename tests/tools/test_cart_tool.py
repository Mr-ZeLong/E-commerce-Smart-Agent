from unittest.mock import AsyncMock

import pytest

from app.models.state import make_agent_state
from app.tools.cart_tool import CartTool


@pytest.fixture
def cart_tool():
    return CartTool()


@pytest.mark.asyncio
async def test_cart_tool_query_empty(cart_tool):
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cart_tool._redis = mock_redis

    state = make_agent_state(question="查看购物车", user_id=42)
    result = await cart_tool.execute(state)

    assert result.output["action"] == "QUERY"
    assert result.output["items"] == []
    assert result.output["total"] == 0.0
    mock_redis.get.assert_awaited_once_with("cart:42")


@pytest.mark.asyncio
async def test_cart_tool_add_item(cart_tool):
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cart_tool._redis = mock_redis

    state = make_agent_state(
        question="加入购物车",
        user_id=1,
        slots={
            "action": "ADD",
            "sku": "SKU-001",
            "product_name": "测试商品",
            "quantity": 2,
            "price": 99.5,
        },
    )
    result = await cart_tool.execute(state)

    assert result.output["action"] == "ADD"
    assert result.output["name"] == "测试商品"
    assert result.output["quantity"] == 2
    assert result.output["total"] == 199.0
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_cart_tool_remove_item(cart_tool):
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"user_id": "1", "items": [{"sku": "SKU-001", "name": "测试商品", "quantity": 1, "price": 10.0, "subtotal": 10.0}], "total": 10.0}'
    cart_tool._redis = mock_redis

    state = make_agent_state(
        question="移除商品",
        user_id=1,
        slots={"action": "REMOVE", "sku": "SKU-001"},
    )
    result = await cart_tool.execute(state)

    assert result.output["action"] == "REMOVE"
    assert result.output["name"] == "测试商品"
    assert result.output["items"] == []
    assert result.output["total"] == 0.0


@pytest.mark.asyncio
async def test_cart_tool_modify_quantity(cart_tool):
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"user_id": "1", "items": [{"sku": "SKU-001", "name": "测试商品", "quantity": 1, "price": 10.0, "subtotal": 10.0}], "total": 10.0}'
    cart_tool._redis = mock_redis

    state = make_agent_state(
        question="修改数量",
        user_id=1,
        slots={"action": "MODIFY", "sku": "SKU-001", "quantity": 3},
    )
    result = await cart_tool.execute(state)

    assert result.output["action"] == "MODIFY"
    assert result.output["quantity"] == 3
    assert result.output["total"] == 30.0


@pytest.mark.asyncio
async def test_cart_tool_add_missing_sku(cart_tool):
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cart_tool._redis = mock_redis

    state = make_agent_state(
        question="加入购物车",
        user_id=1,
        slots={"action": "ADD"},
    )
    result = await cart_tool.execute(state)

    assert result.output["status"] == "error"
    assert "sku" in result.output["reason"] or "product_id" in result.output["reason"]
