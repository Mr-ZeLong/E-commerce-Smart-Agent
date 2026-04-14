import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.confidence.signals import (
    LLMConfidenceScore,
    SignalResult,
    calculate_confidence_signals,
    calculate_emotion_signal,
    calculate_llm_signal,
    calculate_rag_signal,
)


class TestCalculateRAGSignal:
    @pytest.mark.asyncio
    async def test_empty_similarities_returns_zero(self):
        result = await calculate_rag_signal(similarities=[], chunks=[], query="test")
        assert result.score == 0.0
        assert result.reason == "无检索结果"

    @pytest.mark.asyncio
    async def test_normal_similarities_and_chunks(self):
        similarities = [0.8, 0.6, 0.4]
        chunks = ["chunk one", "chunk two", "chunk three"]
        query = "test query"
        result = await calculate_rag_signal(similarities=similarities, chunks=chunks, query=query)
        mapped = [0.5 + s * 0.5 for s in similarities]
        max_sim = max(mapped)
        avg_sim = sum(mapped) / len(mapped)
        assert result.metadata is not None
        score = max_sim * 0.4 + avg_sim * 0.3 + result.metadata["coverage"] * 0.3
        assert result.score == pytest.approx(score, rel=1e-6)
        assert result.metadata["max_similarity"] == max_sim
        assert result.metadata["avg_similarity"] == avg_sim
        assert "coverage" in result.metadata
        assert result.metadata["raw_similarities"] == similarities

    @pytest.mark.asyncio
    async def test_chinese_english_token_extraction_and_coverage(self):
        similarities = [0.9]
        chunks = ["这里有一个 apples 和 bananas"]
        query = "apples 这里"
        result = await calculate_rag_signal(similarities=similarities, chunks=chunks, query=query)
        assert result.metadata is not None
        assert result.metadata["coverage"] == 1.0
        mapped_sim = 0.5 + 0.9 * 0.5
        expected_score = mapped_sim * 0.4 + mapped_sim * 0.3 + 1.0 * 0.3
        assert result.score == pytest.approx(expected_score, rel=1e-6)


class TestCalculateLLMSignal:
    @pytest.fixture
    def mock_llm(self):
        m = AsyncMock()
        m.with_structured_output = MagicMock(return_value=m)
        return m

    @pytest.mark.asyncio
    async def test_calculate_with_float_response(self, mock_llm):
        mock_llm.ainvoke.return_value = LLMConfidenceScore(score=0.75)
        result = await calculate_llm_signal(
            query="q", context=["c"], generated_answer="a", llm=mock_llm
        )
        assert result.score == 0.75
        assert "LLM自评估" in result.reason
        assert result.metadata is not None
        assert result.metadata["raw_response"] == "0.75"

    @pytest.mark.asyncio
    async def test_calculate_with_string_response(self, mock_llm):
        mock_llm.ainvoke.return_value = LLMConfidenceScore(score=0.85)
        result = await calculate_llm_signal(
            query="q", context=["c"], generated_answer="a", llm=mock_llm
        )
        assert result.score == 0.85
        assert "LLM自评估" in result.reason

    @pytest.mark.asyncio
    async def test_calculate_unparseable_raises_type_error(self, mock_llm):
        mock_llm.ainvoke.return_value = {"not_a_float": True}
        with pytest.raises(TypeError, match="Unexpected LLM response type"):
            await calculate_llm_signal(query="q", context=["c"], generated_answer="a", llm=mock_llm)

    @pytest.mark.asyncio
    async def test_calculate_langchain_exception_raises_runtime_error(self, mock_llm):
        from langchain_core.exceptions import LangChainException

        mock_llm.ainvoke.side_effect = LangChainException("boom")
        with pytest.raises(RuntimeError, match="LLM confidence evaluation failed"):
            await calculate_llm_signal(query="q", context=["c"], generated_answer="a", llm=mock_llm)


class TestCalculateEmotionSignal:
    @pytest.fixture(autouse=True)
    def patch_word_lists(self):
        with (
            patch("app.confidence.signals.NEGATIVE_WORDS", {"bad", "angry"}),
            patch("app.confidence.signals.URGENT_WORDS", {"urgent", "hurry"}),
            patch("app.confidence.signals.POSITIVE_WORDS", {"good", "thanks"}),
        ):
            yield

    @pytest.mark.asyncio
    async def test_neutral(self):
        result = await calculate_emotion_signal(query="hello world", history=[])
        assert result.score == 0.7
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "neutral"

    @pytest.mark.asyncio
    async def test_mild_frustration(self):
        result = await calculate_emotion_signal(query="this is bad", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "mild_frustration"
        assert result.score == pytest.approx(0.5, rel=1e-6)

    @pytest.mark.asyncio
    async def test_high_frustration(self):
        result = await calculate_emotion_signal(query="bad angry urgent hurry", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "high_frustration"
        assert result.score < 0.3

    @pytest.mark.asyncio
    async def test_positive(self):
        result = await calculate_emotion_signal(query="good job", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "positive"
        assert result.score > 0.8


class TestCalculateConfidenceSignals:
    @pytest.fixture
    def mock_llm(self):
        m = AsyncMock()
        m.with_structured_output = MagicMock(return_value=m)
        return m

    @pytest.fixture
    def retrieval_state(self):
        return {
            "question": "test question",
            "history": [],
            "retrieval_result": {
                "chunks": ["chunk1"],
                "similarities": [0.8],
                "sources": ["s1"],
            },
        }

    @pytest.fixture
    def no_retrieval_state(self):
        return {"question": "test question", "history": [], "retrieval_result": None}

    @pytest.mark.asyncio
    async def test_calculate_all_with_retrieval_result(self, mock_llm, retrieval_state):
        mock_llm.ainvoke.return_value = LLMConfidenceScore(score=0.8)
        with patch("app.confidence.signals.settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS", 3):
            results = await calculate_confidence_signals(
                retrieval_state, generated_answer="answer", llm=mock_llm
            )

        assert "rag" in results
        assert "emotion" in results
        assert "llm" in results
        assert results["rag"].score > 0
        assert results["llm"].score == 0.8

    @pytest.mark.asyncio
    async def test_calculate_all_without_retrieval_result(self, no_retrieval_state, mock_llm):
        mock_llm.ainvoke.return_value = LLMConfidenceScore(score=0.6)
        with patch("app.confidence.signals.settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS", 3):
            results = await calculate_confidence_signals(
                no_retrieval_state, generated_answer="answer", llm=mock_llm
            )

        assert results["rag"].score == 0.0
        assert results["rag"].reason == "无检索结果"
        assert "emotion" in results
        assert "llm" in results

    @pytest.mark.asyncio
    async def test_calculate_all_skips_llm_when_clear_rag(self, retrieval_state):
        with (
            patch("app.confidence.signals.settings.CONFIDENCE.SKIP_LLM_ON_CLEAR_RAG", True),
            patch("app.confidence.signals.settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_HIGH", 0.9),
            patch("app.confidence.signals.settings.CONFIDENCE.CLEAR_RAG_THRESHOLD_LOW", 0.3),
            patch("app.confidence.signals.settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS", 3),
            patch(
                "app.confidence.signals.calculate_rag_signal",
                new=AsyncMock(return_value=SignalResult(score=0.95, reason="high")),
            ),
        ):
            results = await calculate_confidence_signals(retrieval_state, generated_answer=None)

        assert results["llm"].score == 0.95
        assert results["llm"].metadata is not None
        assert results["llm"].metadata["skipped"] is True

    @pytest.mark.asyncio
    async def test_calculate_all_timeout(self, retrieval_state, mock_llm):
        async def _slow_calculate(*_args, **_kwargs):
            await asyncio.sleep(10)
            return SignalResult(score=0.0, reason="slow")

        with (
            patch(
                "app.confidence.signals.calculate_rag_signal",
                new=_slow_calculate,
            ),
            patch(
                "app.confidence.signals.calculate_emotion_signal",
                new=_slow_calculate,
            ),
            patch(
                "app.confidence.signals.calculate_llm_signal",
                new=_slow_calculate,
            ),
            patch(
                "app.confidence.signals.settings.CONFIDENCE.CALCULATION_TIMEOUT_SECONDS",
                0.001,
            ),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            await calculate_confidence_signals(
                retrieval_state, generated_answer="answer", llm=mock_llm
            )
