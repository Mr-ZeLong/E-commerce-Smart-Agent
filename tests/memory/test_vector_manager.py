import pytest
from qdrant_client import models
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.memory.vector_manager import VectorMemoryManager


class DeterministicEmbedder:
    async def aembed_documents(self, texts):
        return [[0.1] * 1024 for _ in texts]


@pytest.fixture
def deterministic_embedder():
    return DeterministicEmbedder()


@pytest.mark.asyncio
async def test_ensure_collection_already_exists(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name

    await manager.ensure_collection()
    await manager.ensure_collection()

    assert await client.collection_exists(collection_name)


@pytest.mark.asyncio
async def test_ensure_collection_creates_when_missing(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name

    assert not await client.collection_exists(collection_name)
    await manager.ensure_collection()
    assert await client.collection_exists(collection_name)


@pytest.mark.asyncio
async def test_upsert_message(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name
    await manager.ensure_collection()

    await manager.upsert_message(
        user_id=1,
        thread_id="t1",
        message_role="user",
        content="hello",
        timestamp="2024-01-01T00:00:00Z",
        intent="GREETING",
    )

    response = await client.query_points(
        collection_name=collection_name,
        query=[0.1] * 1024,
        using="dense",
        limit=10,
        with_payload=True,
    )

    assert len(response.points) == 1
    payload = response.points[0].payload
    assert payload["content"] == "hello"
    assert payload["intent"] == "GREETING"
    assert payload["user_id"] == 1
    assert payload["thread_id"] == "t1"
    assert payload["message_role"] == "user"


@pytest.mark.asyncio
async def test_search_similar(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name
    await manager.ensure_collection()

    await manager.upsert_message(
        user_id=1,
        thread_id="t1",
        message_role="user",
        content="previous hello",
        timestamp="2024-01-01T00:00:00Z",
    )

    results = await manager.search_similar(user_id=1, query_text="hello", top_k=3)

    assert len(results) == 1
    assert results[0]["content"] == "previous hello"
    assert results[0]["user_id"] == 1
    assert results[0]["message_role"] == "user"


@pytest.mark.asyncio
async def test_search_similar_no_collection(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name

    results = await manager.search_similar(user_id=1, query_text="hello")
    assert results == []


@pytest.mark.asyncio
async def test_prune_old_messages(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name
    await manager.ensure_collection()

    old_timestamp = "2020-01-01T00:00:00+00:00"
    new_timestamp = "2099-01-01T00:00:00+00:00"

    await manager.upsert_message(
        user_id=1,
        thread_id="t1",
        message_role="user",
        content="old message",
        timestamp=old_timestamp,
    )
    await manager.upsert_message(
        user_id=1,
        thread_id="t1",
        message_role="user",
        content="new message",
        timestamp=new_timestamp,
    )

    await manager.prune_old_messages(retention_days=30)

    response = await client.query_points(
        collection_name=collection_name,
        query=[0.1] * 1024,
        using="dense",
        limit=10,
        with_payload=True,
    )

    assert len(response.points) == 1
    assert response.points[0].payload["content"] == "new message"


@pytest.mark.asyncio
async def test_prune_old_messages_collection_missing(qdrant_client, deterministic_embedder):
    client, collection_name = qdrant_client
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name

    await manager.prune_old_messages(retention_days=30)


@pytest.mark.asyncio
async def test_aclose(deterministic_embedder):
    from app.core.config import settings
    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=settings.QDRANT_TIMEOUT,
    )
    collection_name = "test_aclose_collection"
    manager = VectorMemoryManager(client=client, embedder=deterministic_embedder)
    manager.COLLECTION_NAME = collection_name

    await manager.aclose()
