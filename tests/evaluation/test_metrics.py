from unittest.mock import AsyncMock

import pytest

from app.evaluation.metrics import (
    batch_rag_precision,
    rag_precision,
)


@pytest.mark.asyncio
async def test_rag_precision_heuristic_exact_match():
    chunks = ["退换货政策: 7天无理由", "其他信息"]
    result = await rag_precision("退换货政策", chunks, llm_judge=False)
    assert result == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_rag_precision_heuristic_token_match():
    chunks = ["关于发货时效的说明", "其他信息"]
    result = await rag_precision("发货时效", chunks, llm_judge=False)
    assert result == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_rag_precision_heuristic_no_match():
    chunks = ["不相关的内容", "其他信息"]
    result = await rag_precision("退换货政策", chunks, llm_judge=False)
    assert result == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_rag_precision_heuristic_empty_chunks():
    result = await rag_precision("query", [], llm_judge=False)
    assert result == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_parses_json_scores(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", '{"scores": [0.8, 0.6, 0.9]}'),
    ]
    chunks = ["chunk1", "chunk2", "chunk3"]
    result = await rag_precision("question", chunks, llm_judge=True, llm=deterministic_llm)
    assert result == pytest.approx((0.8 + 0.6 + 0.9) / 3)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_parses_inline_scores(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", "The scores are: 0.7, 0.5, 1.0"),
    ]
    chunks = ["chunk1", "chunk2", "chunk3"]
    result = await rag_precision("question", chunks, llm_judge=True, llm=deterministic_llm)
    assert result == pytest.approx((0.7 + 0.5 + 1.0) / 3)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_clamps_to_valid_range(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", '{"scores": [1.5, -0.2, 0.8]}'),
    ]
    chunks = ["chunk1", "chunk2", "chunk3"]
    result = await rag_precision("question", chunks, llm_judge=True, llm=deterministic_llm)
    assert 0.0 <= result <= 1.0
    assert result == pytest.approx((1.0 + 0.0 + 0.8) / 3)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_handles_fewer_chunks(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", '{"scores": [0.9]}'),
    ]
    chunks = ["chunk1"]
    result = await rag_precision("question", chunks, llm_judge=True, llm=deterministic_llm)
    assert result == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_fallback_on_parse_failure(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", "invalid response with no scores"),
    ]
    chunks = ["chunk1", "chunk2", "chunk3"]
    result = await rag_precision("question", chunks, llm_judge=True, llm=deterministic_llm)
    assert result == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_fallback_on_exception(deterministic_llm):
    deterministic_llm.exception = Exception("LLM failure")
    chunks = ["chunk1", "chunk2", "chunk3"]
    result = await rag_precision("question", chunks, llm_judge=True, llm=deterministic_llm)
    assert result == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_rag_precision_llm_judge_fallback_without_llm(caplog):
    chunks = ["chunk1", "chunk2", "chunk3"]
    with caplog.at_level("WARNING"):
        result = await rag_precision("question", chunks, llm_judge=True, llm=None)
    assert "requires an LLM" in caplog.text
    assert result == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_batch_rag_precision_empty_chunks(deterministic_llm):
    questions = ["q1", "q2"]
    chunks_list = [[], []]
    results = await batch_rag_precision(questions, chunks_list, deterministic_llm)
    assert results == [0.0, 0.0]


@pytest.mark.asyncio
async def test_batch_rag_precision_single_item(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", '{"scores": [0.9, 0.8, 0.7]}'),
    ]
    questions = ["q1"]
    chunks_list = [["c1", "c2", "c3"]]
    results = await batch_rag_precision(questions, chunks_list, deterministic_llm)
    assert len(results) == 1
    assert results[0] == pytest.approx((0.9 + 0.8 + 0.7) / 3)


@pytest.mark.asyncio
async def test_batch_rag_precision_multiple_items(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", '{"scores": [1.0, 0.5, 0.0]}'),
    ]
    questions = ["q1", "q2"]
    chunks_list = [["c1", "c2", "c3"], ["c4", "c5", "c6"]]
    results = await batch_rag_precision(questions, chunks_list, deterministic_llm)
    assert len(results) == 2
    assert all(r == pytest.approx((1.0 + 0.5 + 0.0) / 3) for r in results)


@pytest.mark.asyncio
async def test_batch_rag_precision_graceful_failure(deterministic_llm):
    deterministic_llm.exception = Exception("LLM failure")
    questions = ["q1", "q2"]
    chunks_list = [["c1", "c2"], ["c3", "c4"]]
    results = await batch_rag_precision(questions, chunks_list, deterministic_llm)
    assert results == [0.0, 0.0]


@pytest.mark.asyncio
async def test_batch_rag_precision_mixed_results(deterministic_llm):
    deterministic_llm.responses = [
        ("relevance", '{"scores": [0.9]}'),
    ]
    questions = ["q1", "q2", "q3"]
    chunks_list = [["c1"], [], ["c2", "c3"]]
    results = await batch_rag_precision(questions, chunks_list, deterministic_llm)
    assert len(results) == 3
    assert results[0] == pytest.approx(0.9)
    assert results[1] == pytest.approx(0.0)
    assert results[2] == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_batch_rag_precision_respects_max_concurrency():
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=AsyncMock(content='{"scores": [0.5]}'))

    questions = ["q1", "q2", "q3"]
    chunks_list = [["c1"], ["c2"], ["c3"]]

    results = await batch_rag_precision(questions, chunks_list, mock_llm, max_concurrency=2)
    assert len(results) == 3
    assert mock_llm.ainvoke.call_count == 3


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_rag_precision(real_llm):
    chunks = ["退换货政策: 7天无理由退货", "发货时效: 1-3天", "其他信息"]
    result = await rag_precision("退换货政策", chunks, llm_judge=True, llm=real_llm)
    assert 0.0 <= result <= 1.0
