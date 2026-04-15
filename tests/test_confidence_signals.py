import pytest

from app.confidence.signals import (
    ConfidenceSignalCalculator,
    LLMConfidenceScore,
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
    @pytest.mark.asyncio
    async def test_calculate_with_float_response(self, deterministic_llm):
        deterministic_llm.structured = {"LLMConfidenceScore": LLMConfidenceScore(score=0.75)}
        result = await calculate_llm_signal(
            query="q", context=["c"], generated_answer="a", llm=deterministic_llm
        )
        assert result.score == 0.75
        assert "LLM自评估" in result.reason
        assert result.metadata is not None
        assert result.metadata["raw_response"] == "0.75"

    @pytest.mark.asyncio
    async def test_calculate_with_string_response(self, deterministic_llm):
        deterministic_llm.structured = {"LLMConfidenceScore": LLMConfidenceScore(score=0.85)}
        result = await calculate_llm_signal(
            query="q", context=["c"], generated_answer="a", llm=deterministic_llm
        )
        assert result.score == 0.85
        assert "LLM自评估" in result.reason

    @pytest.mark.asyncio
    async def test_calculate_unparseable_raises_type_error(self, deterministic_llm):
        deterministic_llm.structured = {"LLMConfidenceScore": {"not_a_float": True}}
        with pytest.raises(TypeError, match="Unexpected LLM response type"):
            await calculate_llm_signal(
                query="q", context=["c"], generated_answer="a", llm=deterministic_llm
            )

    @pytest.mark.asyncio
    async def test_calculate_langchain_exception_raises_runtime_error(self):
        from langchain_core.exceptions import LangChainException

        from tests._llm import DeterministicChatModel

        class FailingLLM(DeterministicChatModel):
            def with_structured_output(self, schema, **kwargs):
                class _FailingRunnable:
                    async def ainvoke(self, input, config=None, **kwargs):
                        raise LangChainException("boom")

                return _FailingRunnable()

        llm = FailingLLM()
        with pytest.raises(RuntimeError, match="LLM confidence evaluation failed"):
            await calculate_llm_signal(query="q", context=["c"], generated_answer="a", llm=llm)


class TestCalculateEmotionSignal:
    @pytest.mark.asyncio
    async def test_neutral(self):
        calc = ConfidenceSignalCalculator(
            negative_words={"bad", "angry"},
            urgent_words={"urgent", "hurry"},
            positive_words={"good", "thanks"},
            history_rounds=3,
        )
        result = await calc.calculate_emotion_signal(query="hello world", history=[])
        assert result.score == 0.7
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "neutral"

    @pytest.mark.asyncio
    async def test_mild_frustration(self):
        calc = ConfidenceSignalCalculator(
            negative_words={"bad", "angry"},
            urgent_words={"urgent", "hurry"},
            positive_words={"good", "thanks"},
            history_rounds=3,
        )
        result = await calc.calculate_emotion_signal(query="this is bad", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "mild_frustration"
        assert result.score == pytest.approx(0.5, rel=1e-6)

    @pytest.mark.asyncio
    async def test_high_frustration(self):
        calc = ConfidenceSignalCalculator(
            negative_words={"bad", "angry"},
            urgent_words={"urgent", "hurry"},
            positive_words={"good", "thanks"},
            history_rounds=3,
        )
        result = await calc.calculate_emotion_signal(query="bad angry urgent hurry", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "high_frustration"
        assert result.score < 0.3

    @pytest.mark.asyncio
    async def test_positive(self):
        calc = ConfidenceSignalCalculator(
            negative_words={"bad", "angry"},
            urgent_words={"urgent", "hurry"},
            positive_words={"good", "thanks"},
            history_rounds=3,
        )
        result = await calc.calculate_emotion_signal(query="good job", history=[])
        assert result.metadata is not None
        assert result.metadata["emotion_type"] == "positive"
        assert result.score > 0.8
