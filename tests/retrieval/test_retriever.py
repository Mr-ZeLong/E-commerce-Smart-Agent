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
async def test_retriever_sparse_embedder_failure_propagates():
    rewriter = AsyncMock()
    rewriter.rewrite.return_value = "改写后"

    qdrant_client = AsyncMock()

    dense_embedder = AsyncMock()
    dense_embedder.aembed_query.return_value = [0.1] * 1024

    sparse_embedder = AsyncMock()
    sparse_embedder.aembed.side_effect = ConnectionError("sparse fail")

    reranker = AsyncMock()

    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        reranker=reranker,
        rewriter=rewriter,
    )

    with pytest.raises(ConnectionError, match="sparse fail"):
        await retriever.retrieve("怎么退货")


@pytest.mark.asyncio
async def test_retriever_reranker_failure_propagates():
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
    reranker.rerank.side_effect = ConnectionError("rerank fail")

    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        reranker=reranker,
        rewriter=rewriter,
    )

    with pytest.raises(ConnectionError, match="rerank fail"):
        await retriever.retrieve("怎么退货")
