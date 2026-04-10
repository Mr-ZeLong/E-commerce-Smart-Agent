from unittest.mock import AsyncMock

import pytest

from app.retrieval.retriever import HybridRetriever


@pytest.mark.asyncio
async def test_retriever_orchestrates_all_steps():
    rewriter = AsyncMock()
    rewriter.rewrite.return_value = "改写后"

    qdrant_client = AsyncMock()
    qdrant_client.query_hybrid.return_value = [
        type(
            "P",
            (),
            {
                "id": 1,
                "score": 0.1,
                "payload": {"content": "c1", "source": "s1", "meta_data": {}},
            },
        )(),
        type(
            "P",
            (),
            {
                "id": 2,
                "score": 0.05,
                "payload": {"content": "c2", "source": "s2", "meta_data": {}},
            },
        )(),
    ]

    dense_embedder = AsyncMock()
    dense_embedder.aembed_query.return_value = [0.1] * 1024

    sparse_embedder = AsyncMock()
    sparse_embedder.aembed.return_value = [AsyncMock(indices=[0], values=[1.0])]

    reranker = AsyncMock()
    reranker.rerank.return_value = [
        type("R", (), {"index": 0, "score": 0.99})(),
        type("R", (), {"index": 1, "score": 0.88})(),
    ]

    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        reranker=reranker,
        rewriter=rewriter,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 2
    assert results[0].content == "c1"
    assert results[0].score == pytest.approx(0.99)
    qdrant_client.query_hybrid.assert_called_once()


@pytest.mark.asyncio
async def test_retriever_fallback_to_dense_when_sparse_fails():
    rewriter = AsyncMock()
    rewriter.rewrite.return_value = "改写后"

    qdrant_client = AsyncMock()
    qdrant_client.query_dense.return_value = [
        type(
            "P",
            (),
            {
                "id": 1,
                "score": 0.2,
                "payload": {"content": "dense_only", "source": "s1"},
            },
        )(),
    ]

    dense_embedder = AsyncMock()
    dense_embedder.aembed_query.return_value = [0.1] * 1024

    sparse_embedder = AsyncMock()
    sparse_embedder.aembed.side_effect = RuntimeError("sparse fail")

    reranker = AsyncMock()
    reranker.rerank.return_value = [
        type("R", (), {"index": 0, "score": 0.95})(),
    ]

    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        reranker=reranker,
        rewriter=rewriter,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 1
    assert results[0].content == "dense_only"
    qdrant_client.query_dense.assert_called_once()


@pytest.mark.asyncio
async def test_retriever_fallback_to_qdrant_scores_when_rerank_fails():
    rewriter = AsyncMock()
    rewriter.rewrite.return_value = "改写后"

    qdrant_client = AsyncMock()
    qdrant_client.query_hybrid.return_value = [
        type(
            "P",
            (),
            {
                "id": 1,
                "score": 0.77,
                "payload": {"content": "c1", "source": "s1", "meta_data": {}},
            },
        )(),
    ]

    dense_embedder = AsyncMock()
    dense_embedder.aembed_query.return_value = [0.1] * 1024

    sparse_embedder = AsyncMock()
    sparse_embedder.aembed.return_value = [AsyncMock(indices=[0], values=[1.0])]

    reranker = AsyncMock()
    reranker.rerank.side_effect = RuntimeError("rerank fail")

    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        reranker=reranker,
        rewriter=rewriter,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 1
    assert results[0].content == "c1"
    assert results[0].score == pytest.approx(0.77)
