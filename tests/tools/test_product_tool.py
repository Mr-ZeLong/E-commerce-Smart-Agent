import pytest
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.models.state import make_agent_state
from app.tools.product_tool import ProductTool


class DeterministicEmbedder:
    async def aembed_query(self, _text):
        return [0.1] * 1024


class DeterministicRewriter:
    def __init__(self):
        self.calls = []

    async def rewrite(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return query


@pytest.mark.asyncio
async def test_product_tool_collection_not_exists(qdrant_client):
    client, collection_name = qdrant_client
    await client.delete_collection(collection_name)
    tool = ProductTool(
        qdrant_client=client,
        embedder=DeterministicEmbedder(),
        collection_name=collection_name,
    )
    state = make_agent_state(question="推荐手机")
    result = await tool.execute(state)

    assert result.output["status"] == "not_found"
    assert "尚未初始化" in result.output["reason"]


@pytest.mark.asyncio
async def test_product_tool_search_returns_products(qdrant_client):
    client, collection_name = qdrant_client
    await client.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    )
    await client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=1,
                vector={"dense": [0.1] * 1024},
                payload={
                    "name": "智能手机 Pro",
                    "description": "旗舰手机",
                    "price": 4999.0,
                    "category": "数码",
                    "sku": "PHONE-003",
                    "in_stock": True,
                    "attributes": {"屏幕": "6.7英寸"},
                },
            )
        ],
    )
    tool = ProductTool(
        qdrant_client=client,
        embedder=DeterministicEmbedder(),
        collection_name=collection_name,
    )
    state = make_agent_state(question="推荐手机")
    result = await tool.execute(state)

    assert result.output["status"] == "success"
    assert len(result.output["products"]) == 1
    assert result.output["products"][0]["name"] == "智能手机 Pro"
    assert result.output["direct_answer"] is None


@pytest.mark.asyncio
async def test_product_tool_direct_answer_from_attributes(qdrant_client):
    client, collection_name = qdrant_client
    await client.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    )
    await client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=1,
                vector={"dense": [0.1] * 1024},
                payload={
                    "name": "智能手机 Pro",
                    "description": "旗舰手机",
                    "price": 4999.0,
                    "category": "数码",
                    "sku": "PHONE-003",
                    "in_stock": True,
                    "attributes": {"屏幕": "6.7英寸 OLED"},
                },
            )
        ],
    )
    tool = ProductTool(
        qdrant_client=client,
        embedder=DeterministicEmbedder(),
        collection_name=collection_name,
    )
    state = make_agent_state(question="屏幕多大？")
    result = await tool.execute(state)

    assert result.output["status"] == "success"
    assert "direct_answer" in result.output
    assert result.output["direct_answer"] is not None
    assert "6.7英寸" in result.output["direct_answer"]


@pytest.mark.asyncio
async def test_product_tool_with_filters(qdrant_client):
    client, collection_name = qdrant_client
    await client.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    )
    await client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=1,
                vector={"dense": [0.1] * 1024},
                payload={
                    "name": "智能手机 Pro",
                    "description": "旗舰手机",
                    "price": 4999.0,
                    "category": "数码",
                    "sku": "PHONE-003",
                    "in_stock": True,
                    "attributes": {},
                },
            ),
            PointStruct(
                id=2,
                vector={"dense": [0.2] * 1024},
                payload={
                    "name": "普通耳机",
                    "description": "有线耳机",
                    "price": 99.0,
                    "category": "配件",
                    "sku": "EAR-001",
                    "in_stock": True,
                    "attributes": {},
                },
            ),
        ],
    )
    tool = ProductTool(
        qdrant_client=client,
        embedder=DeterministicEmbedder(),
        collection_name=collection_name,
    )
    state = make_agent_state(
        question="推荐数码产品",
        slots={"category": "数码", "min_price": 1000, "max_price": 6000, "in_stock": True},
    )
    result = await tool.execute(state)

    assert result.output["status"] == "success"
    assert len(result.output["products"]) == 1
    assert result.output["products"][0]["category"] == "数码"
    assert result.output["products"][0]["name"] == "智能手机 Pro"


@pytest.mark.asyncio
async def test_product_tool_uses_rewriter_when_available(qdrant_client):
    client, collection_name = qdrant_client
    await client.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    )
    await client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=1,
                vector={"dense": [0.1] * 1024},
                payload={
                    "name": "智能手机 Pro",
                    "description": "旗舰手机",
                    "price": 4999.0,
                    "category": "数码",
                    "sku": "PHONE-003",
                    "in_stock": True,
                    "attributes": {},
                },
            )
        ],
    )
    rewriter = DeterministicRewriter()
    tool = ProductTool(
        qdrant_client=client,
        rewriter=rewriter,
        embedder=DeterministicEmbedder(),
        collection_name=collection_name,
    )
    state = make_agent_state(
        question="推荐手机",
        history=[{"role": "user", "content": "预算5000"}],
    )
    result = await tool.execute(state)

    assert result.output["status"] == "success"
    assert result.output["query"] == "推荐手机"
    assert len(rewriter.calls) == 1
    assert rewriter.calls[0][0] == "推荐手机"
    assert rewriter.calls[0][1].get("conversation_history") == [
        {"role": "user", "content": "预算5000"}
    ]
