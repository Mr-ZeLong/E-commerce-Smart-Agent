from unittest.mock import AsyncMock, patch

import pytest

from app.retrieval.rewriter import QueryRewriter


@pytest.mark.asyncio
async def test_rewrite_returns_first_line():
    with patch("app.core.llm_factory.ChatOpenAI") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = type("R", (), {"content": "  \n改写后查询\n多余内容"})()
        mock_llm_cls.return_value = mock_llm

        rewriter = QueryRewriter(base_url="http://test", api_key="sk-test")
        result = await rewriter.rewrite("东西坏了怎么退")
        assert result == "改写后查询"


@pytest.mark.asyncio
async def test_rewrite_fallback_on_exception():
    with patch("app.core.llm_factory.ChatOpenAI") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = RuntimeError("LLM error")
        mock_llm_cls.return_value = mock_llm

        rewriter = QueryRewriter(base_url="http://test", api_key="sk-test")
        result = await rewriter.rewrite("东西坏了怎么退")
        assert result == "东西坏了怎么退"


@pytest.mark.asyncio
async def test_rewrite_fallback_on_empty_response():
    with patch("app.core.llm_factory.ChatOpenAI") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = type("R", (), {"content": "   \n   \n  "})()
        mock_llm_cls.return_value = mock_llm

        rewriter = QueryRewriter(base_url="http://test", api_key="sk-test")
        result = await rewriter.rewrite("东西坏了怎么退")
        assert result == "东西坏了怎么退"
