import pytest

from app.evaluation.hallucination import (
    evaluate_hallucination_rate,
    has_required_citations,
    heuristic_hallucination_score,
    llm_hallucination_score,
)


def test_has_required_citations_with_citation():
    assert has_required_citations("Answer [来源: A] here") is True


def test_has_required_citations_without_citation():
    assert has_required_citations("Answer without citation") is False


def test_heuristic_hallucination_score_no_chunks():
    assert heuristic_hallucination_score("Any answer", []) == 1.0


def test_heuristic_hallucination_score_with_citation():
    assert heuristic_hallucination_score("Answer [来源: A]", ["chunk"]) == 1.0


def test_heuristic_hallucination_score_without_citation():
    assert heuristic_hallucination_score("Answer without citation", ["chunk"]) == 0.0


@pytest.mark.asyncio
async def test_evaluate_hallucination_rate_meets_target():
    records = [
        {"question": "q1", "answer": "A [来源: 1]", "chunks": ["c1"]},
        {"question": "q2", "answer": "B [来源: 2]", "chunks": ["c2"]},
    ]
    result = await evaluate_hallucination_rate(records)
    assert result["hallucination_rate"] == 0.0
    assert result["meets_target"] is True
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_evaluate_hallucination_rate_exceeds_target():
    records = [
        {"question": "q1", "answer": "A [来源: 1]", "chunks": ["c1"]},
        {"question": "q2", "answer": "B without citation", "chunks": ["c2"]},
    ]
    result = await evaluate_hallucination_rate(records)
    assert result["hallucination_rate"] == 0.5
    assert result["meets_target"] is False
    assert result["hallucinated_count"] == 1


@pytest.mark.asyncio
async def test_llm_hallucination_score_no_hallucination():
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="1"))
    score = await llm_hallucination_score("q", "Answer with [来源: A].", ["chunk"], mock_llm)
    assert score == 1.0


@pytest.mark.asyncio
async def test_llm_hallucination_score_hallucination():
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="0"))
    score = await llm_hallucination_score("q", "Answer without support.", ["chunk"], mock_llm)
    assert score == 0.0


@pytest.mark.asyncio
async def test_llm_hallucination_score_fallback_on_exception():
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM failed"))
    score = await llm_hallucination_score("q", "Answer.", ["chunk"], mock_llm)
    assert score == 0.0


@pytest.mark.asyncio
async def test_evaluate_hallucination_rate_with_llm_judge():
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="1"))
    records = [
        {"question": "q1", "answer": "A", "chunks": ["c1"]},
        {"question": "q2", "answer": "B", "chunks": ["c2"]},
    ]
    result = await evaluate_hallucination_rate(records, llm=mock_llm, use_llm_judge=True)
    assert result["hallucination_rate"] == 0.0
    assert result["meets_target"] is True
    assert result["method"] == "llm_judge"


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_hallucination_score(real_llm):
    score = await llm_hallucination_score(
        "运费怎么算？",
        "满100元免运费。",
        ["运费政策: 满100元免运费"],
        real_llm,
    )
    assert 0.0 <= score <= 1.0
