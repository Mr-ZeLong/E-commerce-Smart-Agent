import pytest

from app.retrieval.reranker import QwenReranker
from tests._reranker import DeterministicReranker


def test_qwen_reranker_initialization():
    reranker = QwenReranker(base_url="http://test/", api_key="sk-test", model="test-rerank")
    assert reranker.base_url == "http://test"
    assert reranker.api_key == "sk-test"
    assert reranker.model == "test-rerank"


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
