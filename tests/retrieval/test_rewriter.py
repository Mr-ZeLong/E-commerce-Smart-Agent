import pytest

from app.retrieval.rewriter import QueryRewriter, _MultiQueryResult, _RewrittenQuery


def _make_rewriter_structured(
    rewrite_query: str | None = None, multi_queries: list[str] | None = None
):
    structured: dict = {}
    if rewrite_query is not None:
        structured["_RewrittenQuery"] = _RewrittenQuery(query=rewrite_query)
    if multi_queries is not None:
        structured["_MultiQueryResult"] = _MultiQueryResult(queries=multi_queries)
    return structured


@pytest.mark.asyncio
async def test_rewrite_returns_rewritten_query(deterministic_llm):
    deterministic_llm.responses = [(["原始查询"], "改写后的查询")]
    rewriter = QueryRewriter(llm=deterministic_llm)
    result = await rewriter.rewrite("原始查询")
    assert result == "改写后的查询"


@pytest.mark.asyncio
async def test_rewrite_with_history(deterministic_llm):
    deterministic_llm.responses = [(["怎么退"], "改写后的查询")]
    rewriter = QueryRewriter(llm=deterministic_llm)
    history = [{"role": "user", "content": "之前买了个手机"}]
    result = await rewriter.rewrite("怎么退", conversation_history=history)
    assert result == "改写后的查询"


@pytest.mark.asyncio
async def test_rewrite_cache_hit(deterministic_llm, redis_client):
    deterministic_llm.responses = [(["cache_hit_test_query_unique_12345"], "改写后的查询")]
    rewriter = QueryRewriter(llm=deterministic_llm, redis_client=redis_client)
    query = "cache_hit_test_query_unique_12345"

    result1 = await rewriter.rewrite(query)
    assert result1 == "改写后的查询"

    deterministic_llm.responses = []
    result2 = await rewriter.rewrite(query)
    assert result2 == "改写后的查询"

    cache_key = rewriter._cache_key(query, suffix="single")
    await redis_client.delete(cache_key)


@pytest.mark.asyncio
async def test_rewrite_multi_query(deterministic_llm):
    deterministic_llm.structured = _make_rewriter_structured(
        rewrite_query="", multi_queries=["变体1", "变体2", "变体3"]
    )
    rewriter = QueryRewriter(llm=deterministic_llm)
    result = await rewriter.rewrite_multi("原始查询", n=3)
    assert "变体1" in result
    assert "变体2" in result
    assert "变体3" in result
    assert "原始查询" in result


@pytest.mark.asyncio
async def test_rewrite_cache_miss(deterministic_llm, redis_client):
    deterministic_llm.responses = [(["cache_miss_test_query_unique_67890"], "改写后的查询")]
    rewriter = QueryRewriter(llm=deterministic_llm, redis_client=redis_client)
    query = "cache_miss_test_query_unique_67890"

    result = await rewriter.rewrite(query)
    assert result == "改写后的查询"

    cache_key = rewriter._cache_key(query, suffix="single")
    await redis_client.delete(cache_key)


@pytest.mark.asyncio
async def test_rewrite_fallback_on_failure(deterministic_llm, redis_client):
    deterministic_llm.responses = []
    rewriter = QueryRewriter(llm=deterministic_llm, redis_client=redis_client)
    query = "fallback_test_query_unique"

    result = await rewriter.rewrite(query)
    assert result == query


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_rewrite(real_llm):
    rewriter = QueryRewriter(llm=real_llm)
    result = await rewriter.rewrite("怎么退货")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_rewrite_with_history(real_llm):
    rewriter = QueryRewriter(llm=real_llm)
    history = [{"role": "user", "content": "之前买了个手机"}]
    result = await rewriter.rewrite("怎么退", conversation_history=history)
    assert isinstance(result, str)
    assert len(result) > 0
