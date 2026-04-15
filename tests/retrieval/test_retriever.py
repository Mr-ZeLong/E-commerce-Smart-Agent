import pytest
from qdrant_client import models

from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.reranker import RerankResult
from app.retrieval.retriever import HybridRetriever


class DeterministicRewriter:
    async def rewrite(self, query, **kwargs):
        return f"rewritten:{query}"

    async def rewrite_multi(self, query, **kwargs):
        return [query, f"variant:{query}"]


class DeterministicDenseEmbedder:
    async def aembed_query(self, text):
        return [0.1] * 1024


class DeterministicSparseEmbedder:
    async def aembed(self, texts):
        return [models.SparseVector(indices=[0, 1], values=[1.0, 0.5]) for _ in texts]


class DeterministicReranker:
    async def rerank(self, query, documents, top_n=5):
        return [
            RerankResult(index=i, score=0.99 - i * 0.1) for i in range(min(top_n, len(documents)))
        ]


class FailingSparseEmbedder:
    async def aembed(self, texts):
        raise ConnectionError("sparse fail")


class FailingReranker:
    async def rerank(self, query, documents, top_n=5):
        raise ConnectionError("rerank fail")


class SingleResultReranker:
    async def rerank(self, query, documents, top_n=5):
        return [RerankResult(index=0, score=0.99)]


@pytest.mark.asyncio
async def test_retriever_orchestrates_all_steps(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()
    dense_vec_c1 = [0.1] * 1024
    dense_vec_c2 = [-0.5] * 1024
    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": dense_vec_c1,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": dense_vec_c2,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c2", "source": "s2", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=DeterministicReranker(),
        rewriter=DeterministicRewriter(),
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 2
    contents = {r.content for r in results}
    assert contents == {"c1", "c2"}
    for r in results:
        assert 0.0 <= r.score <= 1.0


@pytest.mark.asyncio
async def test_retriever_sparse_embedder_failure_propagates(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=FailingSparseEmbedder(),
        reranker=DeterministicReranker(),
        rewriter=DeterministicRewriter(),
    )

    with pytest.raises(ConnectionError, match="sparse fail"):
        await retriever.retrieve("怎么退货")


@pytest.mark.asyncio
async def test_retriever_reranker_failure_propagates(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()
    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": [0.1] * 1024,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=FailingReranker(),
        rewriter=DeterministicRewriter(),
    )

    with pytest.raises(ConnectionError, match="rerank fail"):
        await retriever.retrieve("怎么退货")


@pytest.mark.asyncio
async def test_retriever_multi_query_mode(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()
    dense_vec_c1 = [0.1] * 1024
    dense_vec_c2 = [-0.5] * 1024
    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": dense_vec_c1,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": dense_vec_c2,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c2", "source": "s2", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=DeterministicReranker(),
        rewriter=DeterministicRewriter(),
        use_multi_query=True,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 2
    contents = {r.content for r in results}
    assert contents == {"c1", "c2"}
    scores = [r.score for r in results]
    assert scores == pytest.approx([0.99, 0.89])


@pytest.mark.asyncio
async def test_retriever_multi_query_deduplicates(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()
    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": [0.1] * 1024,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "same", "source": "s1", "meta_data": {}},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": [0.1] * 1024,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "same", "source": "s2", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=SingleResultReranker(),
        rewriter=DeterministicRewriter(),
        use_multi_query=True,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 1
    assert results[0].content == "same"
