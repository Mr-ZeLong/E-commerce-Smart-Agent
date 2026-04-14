from unittest.mock import AsyncMock

import pytest

from app.retrieval.rewriter import QueryRewriter, _MultiQueryResult, _RewrittenQuery


def _make_mock_llm(return_value):
    mock_llm = AsyncMock()
    structured_mock = AsyncMock()
    structured_mock.ainvoke.return_value = return_value
    mock_llm.with_structured_output = lambda _schema: structured_mock
    return mock_llm


def _make_mock_llm_multi(return_value):
    mock_llm = AsyncMock()

    def _with_structured_output(schema):
        structured_mock = AsyncMock()
        if schema is _MultiQueryResult:
            structured_mock.ainvoke.return_value = return_value
        else:
            structured_mock.ainvoke.return_value = _RewrittenQuery(query="default")
        return structured_mock

    mock_llm.with_structured_output = _with_structured_output
    return mock_llm


@pytest.mark.asyncio
async def test_rewrite_returns_rewritten_query():
    mock_llm = _make_mock_llm(_RewrittenQuery(query="  改写后查询  "))

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "改写后查询"


@pytest.mark.asyncio
async def test_rewrite_falls_back_to_original_on_llm_error():
    mock_llm = AsyncMock()
    structured_mock = AsyncMock()
    structured_mock.ainvoke.side_effect = ConnectionError("LLM error")
    mock_llm.with_structured_output = lambda _schema: structured_mock

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "东西坏了怎么退"


@pytest.mark.asyncio
async def test_rewrite_falls_back_to_original_on_empty_response():
    mock_llm = _make_mock_llm(_RewrittenQuery(query="   \n   "))

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "东西坏了怎么退"


@pytest.mark.asyncio
async def test_rewrite_falls_back_to_original_on_none_content():
    mock_llm = _make_mock_llm(_RewrittenQuery(query=""))

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "东西坏了怎么退"


@pytest.mark.asyncio
async def test_rewrite_uses_cache_when_available():
    mock_llm = _make_mock_llm(_RewrittenQuery(query="改写后"))
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "cached_result"

    rewriter = QueryRewriter(llm=mock_llm, redis_client=mock_redis)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "cached_result"
    mock_llm.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_rewrite_writes_cache_on_success():
    mock_llm = _make_mock_llm(_RewrittenQuery(query="改写后"))
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    rewriter = QueryRewriter(llm=mock_llm, redis_client=mock_redis)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "改写后"
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_rewrite_multi_returns_variants():
    mock_llm = _make_mock_llm_multi(_MultiQueryResult(queries=["变体A", "变体B"]))

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite_multi("东西坏了怎么退", n=2)
    assert "变体A" in result
    assert "变体B" in result
    assert "东西坏了怎么退" in result


@pytest.mark.asyncio
async def test_rewrite_multi_falls_back_on_error():
    mock_llm = AsyncMock()
    structured_mock = AsyncMock()
    structured_mock.ainvoke.side_effect = ConnectionError("LLM error")

    def _with_structured_output(_schema):
        return structured_mock

    mock_llm.with_structured_output = _with_structured_output

    rewriter = QueryRewriter(llm=mock_llm)
    result = await rewriter.rewrite_multi("东西坏了怎么退", n=2)
    assert result == ["东西坏了怎么退"]


@pytest.mark.asyncio
async def test_rewrite_with_history_includes_context():
    mock_llm = AsyncMock()
    structured_mock = AsyncMock()
    structured_mock.ainvoke.return_value = _RewrittenQuery(query="改写后")
    mock_llm.with_structured_output = lambda _schema: structured_mock

    rewriter = QueryRewriter(llm=mock_llm)
    history = [{"role": "user", "content": "之前买了个手机"}]
    result = await rewriter.rewrite("怎么退", conversation_history=history)
    assert result == "改写后"
    call_messages = structured_mock.ainvoke.call_args.args[0]
    prompt = call_messages[0].content
    assert "之前买了个手机" in prompt
    assert "怎么退" in prompt


@pytest.mark.asyncio
async def test_rewrite_cache_key_includes_history_and_memory():
    mock_llm = _make_mock_llm(_RewrittenQuery(query="改写后"))
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    rewriter = QueryRewriter(llm=mock_llm, redis_client=mock_redis)
    key1 = rewriter._cache_key("怎么退", conversation_history=[{"role": "user", "content": "手机"}])
    key2 = rewriter._cache_key("怎么退", conversation_history=[{"role": "user", "content": "耳机"}])
    key3 = rewriter._cache_key(
        "怎么退", memory_context={"structured_facts": [{"fact_text": "vip"}]}
    )
    assert key1 != key2
    assert key1 != key3
    assert key2 != key3


@pytest.mark.asyncio
async def test_rewrite_cache_handles_bytes_from_redis():
    mock_llm = _make_mock_llm(_RewrittenQuery(query="改写后"))
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b"cached_from_bytes"

    rewriter = QueryRewriter(llm=mock_llm, redis_client=mock_redis)
    result = await rewriter.rewrite("东西坏了怎么退")
    assert result == "cached_from_bytes"
    mock_llm.with_structured_output.assert_not_called()
