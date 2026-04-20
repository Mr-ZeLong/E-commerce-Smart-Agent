import pytest

from app.agents.evaluator import ConfidenceEvaluator
from app.confidence.signals import LLMConfidenceScore
from tests._llm import DeterministicChatModel


@pytest.fixture
def evaluator():
    llm = DeterministicChatModel(structured={"LLMConfidenceScore": LLMConfidenceScore(score=0.85)})
    return ConfidenceEvaluator(llm=llm)


@pytest.mark.asyncio
async def test_evaluator_with_retrieval_high_rag(evaluator):
    result = await evaluator.evaluate(
        question="运费怎么算",
        answer="满100免运费",
        history=[],
        retrieval_result={
            "chunks": ["运费怎么算"],
            "similarities": [1.0],
        },
    )

    assert result["confidence_signals"]["rag"]["score"] > 0.9
    assert result["confidence_signals"]["llm"]["score"] == pytest.approx(1.0)
    assert result["needs_human_transfer"] is False
    assert result["audit_level"] == "none"


@pytest.mark.asyncio
async def test_evaluator_without_retrieval_uses_llm():
    llm = DeterministicChatModel(structured={"LLMConfidenceScore": LLMConfidenceScore(score=0.6)})
    evaluator = ConfidenceEvaluator(llm=llm)

    result = await evaluator.evaluate(
        question="你好",
        answer="您好，有什么可以帮您？",
        history=[],
        retrieval_result=None,
    )

    assert result["confidence_signals"]["rag"]["score"] == 0.0
    assert result["confidence_signals"]["llm"]["score"] == pytest.approx(0.7)
    assert result["confidence_signals"]["emotion"]["score"] == pytest.approx(0.7)
    assert result["audit_level"] == "manual"


@pytest.mark.asyncio
async def test_evaluator_custom_threshold_triggers_transfer():
    llm = DeterministicChatModel(structured={"LLMConfidenceScore": LLMConfidenceScore(score=0.6)})
    evaluator = ConfidenceEvaluator(llm=llm)

    result = await evaluator.evaluate(
        question="你好",
        answer="您好",
        history=[],
        retrieval_result=None,
        confidence_threshold=0.9,
    )

    assert result["needs_human_transfer"] is True
    assert result["audit_level"] == "manual"
    assert result["transfer_reason"] == "置信度不足"


@pytest.mark.asyncio
async def test_evaluator_negative_emotion_lowers_score():
    llm = DeterministicChatModel(structured={"LLMConfidenceScore": LLMConfidenceScore(score=0.9)})
    evaluator = ConfidenceEvaluator(llm=llm)

    result = await evaluator.evaluate(
        question="太差了 生气 愤怒",
        answer="非常抱歉",
        history=[],
        retrieval_result=None,
    )

    emotion_score = result["confidence_signals"]["emotion"]["score"]
    assert emotion_score < 0.5
    assert result["needs_human_transfer"] is True


@pytest.fixture
def real_evaluator(real_llm):
    return ConfidenceEvaluator(llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_evaluator_with_retrieval(real_evaluator):
    result = await real_evaluator.evaluate(
        question="运费怎么算",
        answer="满100免运费",
        history=[],
        retrieval_result={
            "chunks": ["运费怎么算"],
            "similarities": [1.0],
        },
    )
    assert "confidence_signals" in result
    assert "rag" in result["confidence_signals"]
    assert "llm" in result["confidence_signals"]
    assert "emotion" in result["confidence_signals"]
    assert result["confidence_signals"]["rag"]["score"] >= 0.0
    assert result["confidence_signals"]["llm"]["score"] >= 0.0
    assert result["confidence_signals"]["emotion"]["score"] >= 0.0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_evaluator_negative_emotion(real_evaluator):
    result = await real_evaluator.evaluate(
        question="太差了 生气 愤怒",
        answer="非常抱歉",
        history=[],
        retrieval_result=None,
    )
    emotion_score = result["confidence_signals"]["emotion"]["score"]
    assert emotion_score < 0.5
    assert result["needs_human_transfer"] is True
