import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.retrieval.reranker import QwenReranker


@pytest.mark.asyncio
async def test_rerank_parses_results():
    reranker = QwenReranker(base_url="http://test", api_key="sk-test")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        response_mock = MagicMock()
        response_mock.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.7},
            ]
        }
        response_mock.raise_for_status = lambda: None
        mock_post.return_value = response_mock

        results = await reranker.rerank("query", ["doc0", "doc1"], top_n=2)
        assert results[0].index == 1
        assert results[0].score == pytest.approx(0.9)
        assert results[1].index == 0
