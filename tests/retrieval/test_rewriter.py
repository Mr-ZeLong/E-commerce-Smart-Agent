from unittest.mock import AsyncMock

import pytest

from app.retrieval.rewriter import QueryRewriter


@pytest.mark.asyncio
async def test_rewrite_returns_first_line():
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = type("R", (), {"content": "  \n改写后查询\n多余内容"})()

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "改写后查询"


@pytest.mark.asyncio
async def test_rewrite_exception_propagates():
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = ConnectionError("LLM error")

    rewriter = QueryRewriter(llm=mock_llm)
    with pytest.raises(ConnectionError, match="LLM error"):
        await rewriter.rewrite("东西坏了怎么退")


@pytest.mark.asyncio
async def test_rewrite_empty_response_propagates():
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = type("R", (), {"content": "   \n   \n  "})()

    rewriter = QueryRewriter(llm=mock_llm)
    with pytest.raises(RuntimeError, match="Query rewriter returned empty response"):
        await rewriter.rewrite("东西坏了怎么退")
