import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.confidence.signals import (
    ConfidenceSignals,
    EmotionSignal,
    LLMSignal,
    RAGSignal,
    SignalResult,
)


class TestRAGSignal:
    @pytest.mark.asyncio
    async def test_empty_similarities_returns_zero(self):
        signal = RAGSignal()
        result = await signal.calculate(similarities=[], chunks=[], query="test")
        assert result.score == 0.0
        assert result.reason == "无检索结果"

    @pytest.mark.asyncio
    async def test_normal_similarities_and_chunks(self):
        signal = RAGSignal()
        similarities = [0.8, 0.6, 0.4]
        chunks = ["chunk one", "chunk two", "chunk three"]
        query = "test query"
        result = await signal.calculate(similarities=similarities, chunks=chunks, query=query)
        max_sim = 0.8
        avg_sim = 0.6
        assert result.metadata is not None
        score = max_sim * 0.4 + avg_sim * 0.3 + result.metadata["coverage"] * 0.3
        assert result.score == pytest.approx(score, rel=1e-6)
        assert result.metadata["max_similarity"] == max_sim
        assert result.metadata["avg_similarity"] == avg_sim
        assert "coverage" in result.metadata

    @pytest.mark.asyncio
    async def test_chinese_english_token_extraction_and_coverage(self):
        signal = RAGSignal()
        similarities = [0.9]
        chunks = ["这里有一个 apples 和 bananas"]
        query = "apples 这里"
        result = await signal.calculate(similarities=similarities, chunks=chunks, query=query)
        # query tokens: {'这', '里', 'apples'}; covered: '这', '里', 'apples' => coverage=1.0
        assert result.metadata is not None
        assert result.metadata["coverage"] == 1.0
        expected_score = 0.9 * 0.4 + 0.9 * 0.3 + 1.0 * 0.3
        assert result.score == pytest.approx(expected_score, rel=1e-6)


class TestLLMSignal:
    @pytest.fixture
    def mock_llm(self):
        return AsyncMock()

    @pytest.fixture
    def signal(self, mock_llm):
        with patch("app.confidence.signals.create_openai_llm", return_value=mock_llm):
            return LLMSignal()

    def test_parse_confidence_score_decimal(self, signal):
        assert signal._parse_confidence_score("0.85") == 0.85

    def test_parse_confidence_score_percent(self, signal):
        assert signal._parse_confidence_score("85%") == 0.85

    def test_parse_confidence_score_chinese_label(self, signal):
        assert signal._parse_confidence_score("置信度：0.85") == 0.85

    def test_parse_confidence_score_chinese_score(self, signal):
        assert signal._parse_confidence_score("分数是：85") == 0.85

    def test_parse_confidence_score_invalid(self, signal):
        assert signal._parse_confidence_score("abc") is None
        assert signal._parse_confidence_score("") is None

    @pytest.mark.asyncio
    async def test_calculate_parseable_score(self, signal, mock_llm):
        mock_llm.ainvoke.return_value = MagicMock(content="0.75")
        result = await signal.calculate(query="q", context=["c"], generated_answer="a")
        assert result.score == 0.75
        assert "LLM自评估" in result.reason
        assert result.metadata is not None
        assert result.metadata["raw_response"] == "0.75"

    @pytest.mark.asyncio
    async def test_calculate_unparseable_exhausts_retries(self, signal, mock_llm):
        mock_llm.ainvoke.return_value = MagicMock(content="unparseable")
        with (
            patch("app.confidence.signals.settings.CONFIDENCE.LLM_PARSE_MAX_RETRIES", 2),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await signal.calculate(query="q", context=["c"], generated_answer="a")
        assert result.score == 0.5
        assert result.reason == "解析失败，使用默认值"
        assert result.metadata is not None
        assert result.metadata["error"] == "parse_failed"
        assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_calculate_exception_exhausts_retries(self, signal, mock_llm):
        mock_llm.ainvoke.side_effect = RuntimeError("boom")
        with (
            patch("app.confidence.signals.settings.CONFIDENCE.LLM_PARSE_MAX_RETRIES", 2),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await signal.calculate(query="q", context=["c"], generated_answer="a")
        assert result.score == 0.5
        assert result.reason == "解析失败，使用默认值"
        assert result.metadata is not None
        assert "boom" in result.metadata["error"]
        assert mock_llm.ainvoke.call_count == 2


class TestEmotionSignal:
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
        signal = EmotionSignal()
        result = await signal.calculate(query="hello world", history=[])
        assert result.score == 0.7
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "neutral"

    @pytest.mark.asyncio
    async def test_mild_frustration(self):
        signal = EmotionSignal()
        result = await signal.calculate(query="this is bad", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "mild_frustration"
        assert result.score == pytest.approx(0.5, rel=1e-6)

    @pytest.mark.asyncio
    async def test_high_frustration(self):
        signal = EmotionSignal()
        result = await signal.calculate(query="bad angry urgent hurry", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "high_frustration"
        assert result.score < 0.3

    @pytest.mark.asyncio
    async def test_positive(self):
        signal = EmotionSignal()
        result = await signal.calculate(query="good job", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "positive"
        assert result.score > 0.8


class TestConfidenceSignals:
    @pytest.fixture
    def mock_llm(self):
        return AsyncMock()

    @pytest.fixture
    def retrieval_state(self):
        return {
            "question": "test question",
            "history": [],
            "retrieval_result": {"chunks": ["chunk1"], "similarities": [0.8], "sources": ["s1"]},
        }

    @pytest.fixture
    def no_retrieval_state(self):
        return {"question": "test question", "history": [], "retrieval_result": None}

    @pytest.mark.asyncio
    async def test_calculate_all_with_retrieval_result(self, mock_llm, retrieval_state):
        with patch("app.confidence.signals.create_openai_llm", return_value=mock_llm):
            signals = ConfidenceSignals(retrieval_state)
            mock_llm.ainvoke.return_value = MagicMock(content="0.8")
            with patch("app.confidence.signals.settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS", 3):
                results = await signals.calculate_all(generated_answer="answer")

        assert "rag" in results
        assert "emotion" in results
        assert "llm" in results
        assert results["rag"].score > 0
        assert results["llm"].score == 0.8

    @pytest.mark.asyncio
    async def test_calculate_all_without_retrieval_result(self, no_retrieval_state, mock_llm):
        with patch("app.confidence.signals.create_openai_llm", return_value=mock_llm):
            signals = ConfidenceSignals(no_retrieval_state)
            with patch("app.confidence.signals.settings.CONFIDENCE.EMOTION_HISTORY_ROUNDS", 3):
                results = await signals.calculate_all(generated_answer="answer")

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
        ):
            signals = ConfidenceSignals(retrieval_state)
            # Force RAG score high by overriding rag_signal.calculate
            with patch.object(
                signals.rag_signal,
                "calculate",
                new=AsyncMock(return_value=SignalResult(score=0.95, reason="high")),
            ):
                results = await signals.calculate_all(generated_answer=None)

        assert results["llm"].score == 0.95
        assert results["llm"].metadata is not None
        assert results["llm"].metadata["skipped"] is True

    @pytest.mark.asyncio
    async def test_calculate_all_timeout(self, retrieval_state, mock_llm):
        with patch("app.confidence.signals.create_openai_llm", return_value=mock_llm):
            signals = ConfidenceSignals(retrieval_state)

        async def _slow_calculate(generated_answer=None):
            await asyncio.sleep(0.01)

        with (
            patch.object(
                signals,
                "_calculate_with_timeout",
                new=_slow_calculate,
            ),
            patch(
                "app.confidence.signals.settings.CONFIDENCE.CALCULATION_TIMEOUT_SECONDS",
                0.001,
            ),
        ):
            results = await signals.calculate_all(generated_answer="answer")

        assert results["rag"].reason == "计算超时"
        assert results["llm"].reason == "计算超时"
        assert results["emotion"].reason == "计算超时"
