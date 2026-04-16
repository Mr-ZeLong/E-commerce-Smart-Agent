from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.retrieval.reranker import QwenReranker
from tests._reranker import DeterministicReranker


def test_qwen_reranker_initialization():
    reranker = QwenReranker(base_url="http://test/", api_key="sk-test", model="test-rerank")
    assert reranker.base_url == "http://test"
    assert reranker.api_key == "sk-test"
    assert reranker.model == "test-rerank"


@pytest.mark.asyncio
async def test_qwen_reranker_rerank_parses_response():
    reranker = QwenReranker(base_url="http://test/", api_key="sk-test", model="test-rerank")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.80},
        ]
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.retrieval.reranker.httpx.AsyncClient", return_value=mock_client):
        results = await reranker.rerank("query", ["doc0", "doc1"], top_n=2)

    assert len(results) == 2
    assert results[0].index == 1
    assert results[0].score == pytest.approx(0.95)
    assert results[1].index == 0
    assert results[1].score == pytest.approx(0.80)


@pytest.mark.asyncio
async def test_qwen_reranker_truncates_long_documents():
    reranker = QwenReranker(
        base_url="http://test/", api_key="sk-test", model="test-rerank", max_document_chars=10
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.retrieval.reranker.httpx.AsyncClient", return_value=mock_client):
        await reranker.rerank("q", ["a" * 100], top_n=1)

    payload = mock_client.post.call_args.kwargs["json"]
    assert len(payload["documents"][0]) == 10


@pytest.mark.asyncio
async def test_deterministic_reranker_returns_default_results():
    reranker = DeterministicReranker()
    results = await reranker.rerank("query", ["doc0", "doc1", "doc2"], top_n=2)
    assert len(results) == 2
    assert results[0].index == 0
    assert results[0].score == pytest.approx(0.99)
    assert results[1].index == 1
    assert results[1].score == pytest.approx(0.89)


@pytest.mark.asyncio
async def test_deterministic_reranker_uses_injected_results():
    from app.retrieval.reranker import RerankResult

    reranker = DeterministicReranker(
        results=[
            RerankResult(index=2, score=0.95),
            RerankResult(index=0, score=0.80),
        ]
    )
    results = await reranker.rerank("query", ["doc0", "doc1", "doc2"], top_n=5)
    assert len(results) == 2
    assert results[0].index == 2
    assert results[0].score == pytest.approx(0.95)
    assert results[1].index == 0
    assert results[1].score == pytest.approx(0.80)
