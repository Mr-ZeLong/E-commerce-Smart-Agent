import pytest
from qdrant_client import AsyncQdrantClient, models

from app.retrieval.client import QdrantKnowledgeClient


@pytest.mark.asyncio
async def test_ensure_collection_creates_collection():
    client = AsyncQdrantClient(location=":memory:")
    knowledge_client = QdrantKnowledgeClient(
        url=":memory:",
        collection_name="test_knowledge",
        client=client,
    )
    await knowledge_client.ensure_collection()

    collections = await client.get_collections()
    assert "test_knowledge" in [c.name for c in collections.collections]


@pytest.mark.asyncio
async def test_query_hybrid_returns_scored_points_with_payloads():
    client = AsyncQdrantClient(location=":memory:")
    knowledge_client = QdrantKnowledgeClient(
        collection_name="test_hybrid",
        client=client,
    )
    await knowledge_client.ensure_collection()

    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": [0.1] * 1024,
                    "sparse": models.SparseVector(indices=[0], values=[1.0]),
                },
                payload={"content": "doc1", "source": "s1"},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": [0.2] * 1024,
                    "sparse": models.SparseVector(indices=[0], values=[1.0]),
                },
                payload={"content": "doc2", "source": "s2"},
            ),
        ]
    )

    results = await knowledge_client.query_hybrid(
        dense_vector=[0.1] * 1024,
        sparse_vector=models.SparseVector(indices=[0], values=[1.0]),
        limit=2,
    )

    assert len(results) == 2
    for r in results:
        assert r.payload is not None
        assert "content" in r.payload
