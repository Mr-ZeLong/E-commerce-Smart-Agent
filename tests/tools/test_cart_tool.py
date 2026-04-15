import pytest
import pytest_asyncio

from app.models.state import make_agent_state
from app.tools.cart_tool import CartTool


@pytest_asyncio.fixture(loop_scope="function")
async def cart_tool(redis_client):
    prefix = getattr(redis_client, "_test_prefix", "test:")
    return CartTool(redis_client=redis_client, key_prefix=prefix)


@pytest.mark.asyncio
async def test_cart_tool_query_empty(cart_tool, redis_client):
    user_id = 42
    state = make_agent_state(question="查看购物车", user_id=user_id)
    result = await cart_tool.execute(state)

    assert result.output["action"] == "QUERY"
    assert result.output["items"] == []
    assert result.output["total"] == 0.0

    key = f"{cart_tool._key_prefix}cart:{user_id}"
    raw = await redis_client.get(key)
    assert raw is None


@pytest.mark.asyncio
async def test_cart_tool_add_item(cart_tool, redis_client):
    user_id = 1
    state = make_agent_state(
        question="加入购物车",
        user_id=user_id,
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

    key = f"{cart_tool._key_prefix}cart:{user_id}"
    raw = await redis_client.get(key)
    assert raw is not None


@pytest.mark.asyncio
async def test_cart_tool_remove_item(cart_tool, redis_client):
    user_id = 1
    key = f"{cart_tool._key_prefix}cart:{user_id}"
    await redis_client.setex(
        key,
        86400,
        '{"user_id": "1", "items": [{"sku": "SKU-001", "name": "测试商品", "quantity": 1, "price": 10.0, "subtotal": 10.0}], "total": 10.0}',
    )

    state = make_agent_state(
        question="移除商品",
        user_id=user_id,
        slots={"action": "REMOVE", "sku": "SKU-001"},
    )
    result = await cart_tool.execute(state)

    assert result.output["action"] == "REMOVE"
    assert result.output["name"] == "测试商品"
    assert result.output["items"] == []
    assert result.output["total"] == 0.0


@pytest.mark.asyncio
async def test_cart_tool_modify_quantity(cart_tool, redis_client):
    user_id = 1
    key = f"{cart_tool._key_prefix}cart:{user_id}"
    await redis_client.setex(
        key,
        86400,
        '{"user_id": "1", "items": [{"sku": "SKU-001", "name": "测试商品", "quantity": 1, "price": 10.0, "subtotal": 10.0}], "total": 10.0}',
    )

    state = make_agent_state(
        question="修改数量",
        user_id=user_id,
        slots={"action": "MODIFY", "sku": "SKU-001", "quantity": 3},
    )
    result = await cart_tool.execute(state)

    assert result.output["action"] == "MODIFY"
    assert result.output["quantity"] == 3
    assert result.output["total"] == 30.0


@pytest.mark.asyncio
async def test_cart_tool_add_missing_sku(cart_tool):
    user_id = 1
    state = make_agent_state(
        question="加入购物车",
        user_id=user_id,
        slots={"action": "ADD"},
    )
    result = await cart_tool.execute(state)

    assert result.output["status"] == "error"
    assert "sku" in result.output["reason"] or "product_id" in result.output["reason"]
