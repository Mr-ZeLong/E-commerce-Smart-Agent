from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.state import make_agent_state
from app.tools.product_tool import ProductTool


@pytest.fixture
def product_tool():
    return ProductTool()


@pytest.mark.asyncio
async def test_product_tool_collection_not_exists(product_tool):
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False
    product_tool._qdrant = mock_client

    state = make_agent_state(question="推荐手机")
    result = await product_tool.execute(state)

    assert result.output["status"] == "not_found"
    assert "尚未初始化" in result.output["reason"]


@pytest.mark.asyncio
async def test_product_tool_search_returns_products(product_tool):
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    mock_point = MagicMock()
    mock_point.id = 0
    mock_point.score = 0.95
    mock_point.payload = {
        "name": "智能手机 Pro",
        "description": "旗舰手机",
        "price": 4999.0,
        "category": "数码",
        "sku": "PHONE-003",
        "in_stock": True,
        "attributes": {"屏幕": "6.7英寸"},
    }

    mock_result = MagicMock()
    mock_result.points = [mock_point]
    mock_client.query_points.return_value = mock_result
    product_tool._qdrant = mock_client

    mock_embedder = MagicMock()
    mock_embedder.aembed_query = AsyncMock(return_value=[0.1] * 1024)
    with patch("app.retrieval.embeddings.create_embedding_model", return_value=mock_embedder):
        state = make_agent_state(question="推荐手机")
        result = await product_tool.execute(state)

    assert result.output["status"] == "success"
    assert len(result.output["products"]) == 1
    assert result.output["products"][0]["name"] == "智能手机 Pro"
    assert result.output["direct_answer"] is None


@pytest.mark.asyncio
async def test_product_tool_direct_answer_from_attributes(product_tool):
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    mock_point = MagicMock()
    mock_point.id = 0
    mock_point.score = 0.95
    mock_point.payload = {
        "name": "智能手机 Pro",
        "description": "旗舰手机",
        "price": 4999.0,
        "category": "数码",
        "sku": "PHONE-003",
        "in_stock": True,
        "attributes": {"屏幕": "6.7英寸 OLED"},
    }

    mock_result = MagicMock()
    mock_result.points = [mock_point]
    mock_client.query_points.return_value = mock_result
    product_tool._qdrant = mock_client

    mock_embedder = MagicMock()
    mock_embedder.aembed_query = AsyncMock(return_value=[0.1] * 1024)
    with patch("app.retrieval.embeddings.create_embedding_model", return_value=mock_embedder):
        state = make_agent_state(question="屏幕多大？")
        result = await product_tool.execute(state)

    assert result.output["status"] == "success"
    assert "direct_answer" in result.output


@pytest.mark.asyncio
async def test_product_tool_with_filters(product_tool):
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_result = MagicMock()
    mock_result.points = []
    mock_client.query_points.return_value = mock_result
    product_tool._qdrant = mock_client

    mock_embedder = MagicMock()
    mock_embedder.aembed_query = AsyncMock(return_value=[0.1] * 1024)
    with patch("app.retrieval.embeddings.create_embedding_model", return_value=mock_embedder):
        state = make_agent_state(
            question="推荐数码产品",
            slots={"category": "数码", "min_price": 1000, "max_price": 6000, "in_stock": True},
        )
        result = await product_tool.execute(state)

    assert result.output["status"] == "success"
    call_kwargs = mock_client.query_points.call_args.kwargs
    assert call_kwargs["using"] == "dense"


@pytest.mark.asyncio
async def test_product_tool_uses_rewriter_when_available():
    mock_rewriter = AsyncMock()
    mock_rewriter.rewrite.return_value = "改写后的手机推荐"

    tool = ProductTool(rewriter=mock_rewriter)

    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_result = MagicMock()
    mock_result.points = []
    mock_client.query_points.return_value = mock_result
    tool._qdrant = mock_client

    mock_embedder = MagicMock()
    mock_embedder.aembed_query = AsyncMock(return_value=[0.1] * 1024)
    with patch("app.retrieval.embeddings.create_embedding_model", return_value=mock_embedder):
        state = make_agent_state(
            question="推荐手机",
            history=[{"role": "user", "content": "预算5000"}],
        )
        result = await tool.execute(state)

    assert result.output["status"] == "success"
    mock_rewriter.rewrite.assert_awaited_once()
    call_args = mock_rewriter.rewrite.call_args
    assert call_args.args[0] == "推荐手机"
    assert call_args.kwargs.get("conversation_history") == [{"role": "user", "content": "预算5000"}]
