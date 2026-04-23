from unittest.mock import AsyncMock

import pytest

from app.agents.policy import (
    _FALLBACK_RESPONSE,
    POLICY_SYSTEM_PROMPT,
    PolicyAgent,
    SelfRAGResult,
)
from app.models.state import make_agent_state
from tests._agents import DeterministicRetriever
from tests._llm import DeterministicChatModel


class _Result:
    def __init__(self, content, source, score):
        self.content = content
        self.source = source
        self.score = score


def _make_self_rag_llm(adequacy="yes", confidence=0.9, grader_score="yes"):
    return DeterministicChatModel(
        structured={
            "GradeDocuments": {"binary_score": grader_score},
            "RetrievalAdequacy": {
                "adequacy": adequacy,
                "confidence": confidence,
                "reason": "test",
            },
            "SelfReflectionResult": {
                "quality_score": 0.9,
                "is_hallucination": False,
                "issues": [],
                "improvement": "",
            },
            "LLMJudgeResult": {
                "is_safe": True,
                "risk_level": "low",
                "reason": "safe",
            },
        }
    )


@pytest.fixture
def mock_load_config(monkeypatch):
    monkeypatch.setattr(PolicyAgent, "_load_config", AsyncMock())


def test_policy_system_prompt_requires_citation():
    assert "[来源:" in POLICY_SYSTEM_PROMPT
    assert "【强制】" in POLICY_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_policy_agent_uses_retriever(mock_load_config):
    results = [_Result("退换货政策内容", "policy.md", 0.95)]
    retriever = DeterministicRetriever(results=results)
    agent = PolicyAgent(retriever=retriever, llm=_make_self_rag_llm())

    state = make_agent_state(question="怎么退货")
    data = await agent._retrieve_knowledge(state)
    assert data["chunks"] == ["退换货政策内容"]
    assert data["similarities"] == [pytest.approx(0.95)]
    assert data["sources"] == ["policy.md"]
    assert data["self_rag"].retrieval_adequacy == "yes"
    assert data["self_rag"].fallback_triggered is False


@pytest.mark.asyncio
async def test_process_with_rag_context(mock_load_config):
    retriever = DeterministicRetriever(
        results=[
            _Result("运费满100免运费", "policy_doc_1", 0.8),
            _Result("配送时效1-3天", "policy_doc_2", 0.75),
        ]
    )
    llm = DeterministicChatModel(
        responses=[
            (["运费", "配送", "政策"], "运费满100元免运费，配送时效为1-3天。[来源: policy_doc_1]"),
        ],
        structured={
            "RetrievalAdequacy": {"adequacy": "yes", "confidence": 0.9, "reason": "test"},
            "SelfReflectionResult": {
                "quality_score": 0.9,
                "is_hallucination": False,
                "issues": [],
                "improvement": "",
            },
            "LLMJudgeResult": {
                "is_safe": True,
                "risk_level": "low",
                "reason": "safe",
            },
        },
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)

    state = make_agent_state(question="运费怎么算？", user_id=1)
    result = await agent.process(state)

    assert "运费" in result["response"]
    assert result["updated_state"]["retrieval_result"]["chunks"] == [
        "运费满100免运费",
        "配送时效1-3天",
    ]
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["retrieval_adequacy"] == "yes"
    assert self_rag["fallback_triggered"] is False
    assert self_rag["citations_verified"] is True


@pytest.mark.asyncio
async def test_process_with_empty_retrieval(mock_load_config):
    retriever = DeterministicRetriever(results=[])
    llm = DeterministicChatModel(
        responses=[
            (["政策", "意思", "查询"], "抱歉，暂未查询到相关规定"),
        ]
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)

    state = make_agent_state(question="请问这个政策是什么意思？", user_id=1)
    result = await agent.process(state)

    assert "抱歉" in result["response"] or "暂未查询" in result["response"]
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["retrieval_adequacy"] == "no"
    assert self_rag["fallback_triggered"] is True


@pytest.mark.asyncio
async def test_retrieve_knowledge_filters_low_score_chunks(mock_load_config):
    class LowScoreRetriever(DeterministicRetriever):
        async def retrieve(self, query, conversation_history=None, memory_context=None, variant_top_k=None, variant_reranker_enabled=None):
            return [
                _Result("高相关", "doc1", 0.6),
                _Result("低相关", "doc2", 0.3),
                _Result("刚好相关", "doc3", 0.5),
            ]

    agent = PolicyAgent(
        retriever=LowScoreRetriever(), llm=_make_self_rag_llm()
    )
    state = make_agent_state(question="运费政策", user_id=1)
    data = await agent._retrieve_knowledge(state)
    assert "低相关" not in data["chunks"]
    assert len(data["chunks"]) == 2


@pytest.mark.asyncio
async def test_retrieve_knowledge_returns_empty_when_grader_rejects_all(mock_load_config):
    class OneResultRetriever(DeterministicRetriever):
        async def retrieve(self, query, conversation_history=None, memory_context=None, variant_top_k=None, variant_reranker_enabled=None):
            return [_Result("某个文档", "doc1", 0.8)]

    llm = DeterministicChatModel(structured={"GradeDocuments": {"binary_score": "no"}})
    agent = PolicyAgent(retriever=OneResultRetriever(), llm=llm)
    state = make_agent_state(question="退换货", user_id=1)
    data = await agent._retrieve_knowledge(state)
    assert data["chunks"] == []
    assert data["self_rag"].fallback_triggered is True


@pytest.mark.asyncio
async def test_process_self_rag_refusal_when_no_relevant_docs(mock_load_config):
    class OneResultRetriever(DeterministicRetriever):
        async def retrieve(self, query, conversation_history=None, memory_context=None, variant_top_k=None, variant_reranker_enabled=None):
            return [_Result("不相关文档", "doc1", 0.8)]

    llm = DeterministicChatModel(structured={"GradeDocuments": {"binary_score": "no"}})
    agent = PolicyAgent(retriever=OneResultRetriever(), llm=llm)
    state = make_agent_state(question="运费政策", user_id=1)
    result = await agent.process(state)
    assert "抱歉" in result["response"] or "暂未查询" in result["response"]
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["fallback_triggered"] is True


@pytest.mark.asyncio
async def test_self_rag_adequate_retrieval(mock_load_config):
    retriever = DeterministicRetriever(
        results=[_Result("退换货政策: 7天无理由退货", "policy.md", 0.9)]
    )
    llm = DeterministicChatModel(
        responses=[
            (["退换货", "7天"], "支持7天无理由退货。[来源: policy.md]"),
        ],
        structured={
            "RetrievalAdequacy": {"adequacy": "yes", "confidence": 0.95, "reason": "Sufficient"},
            "SelfReflectionResult": {
                "quality_score": 0.95,
                "is_hallucination": False,
                "issues": [],
                "improvement": "",
            },
            "LLMJudgeResult": {
                "is_safe": True,
                "risk_level": "low",
                "reason": "safe",
            },
        },
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)
    state = make_agent_state(question="怎么退货？", user_id=1)
    result = await agent.process(state)

    assert "7天" in result["response"]
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["retrieval_adequacy"] == "yes"
    assert self_rag["adequacy_confidence"] == 0.95
    assert self_rag["fallback_triggered"] is False
    assert self_rag["citations_verified"] is True
    assert self_rag["citation_count"] == 1
    assert self_rag["self_reflection_score"] == 0.95


@pytest.mark.asyncio
async def test_self_rag_inadequate_retrieval(mock_load_config):
    retriever = DeterministicRetriever(
        results=[_Result("部分信息", "doc1", 0.8)]
    )
    llm = DeterministicChatModel(
        structured={
            "GradeDocuments": {"binary_score": "yes"},
            "RetrievalAdequacy": {"adequacy": "no", "confidence": 0.2, "reason": "Not enough info"},
        }
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)
    state = make_agent_state(question="复杂的国际运费政策是什么？", user_id=1)
    result = await agent.process(state)

    assert result["response"] == _FALLBACK_RESPONSE
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["retrieval_adequacy"] == "no"
    assert self_rag["fallback_triggered"] is True
    assert self_rag["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_self_rag_partial_retrieval_with_fallback(mock_load_config):
    retriever = DeterministicRetriever(
        results=[_Result("部分运费信息", "doc1", 0.7)]
    )
    llm = DeterministicChatModel(
        structured={
            "GradeDocuments": {"binary_score": "yes"},
            "RetrievalAdequacy": {
                "adequacy": "partial",
                "confidence": 0.4,
                "reason": "Partial info, low confidence",
            },
        }
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)
    state = make_agent_state(question="详细运费政策？", user_id=1)
    result = await agent.process(state)

    assert result["response"] == _FALLBACK_RESPONSE
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["retrieval_adequacy"] == "partial"
    assert self_rag["fallback_triggered"] is True


@pytest.mark.asyncio
async def test_self_rag_partial_retrieval_without_fallback(mock_load_config):
    retriever = DeterministicRetriever(
        results=[_Result("部分运费信息", "doc1", 0.7)]
    )
    llm = DeterministicChatModel(
        responses=[
            (["运费"], "运费满100免运费。[来源: doc1]"),
        ],
        structured={
            "GradeDocuments": {"binary_score": "yes"},
            "RetrievalAdequacy": {
                "adequacy": "partial",
                "confidence": 0.8,
                "reason": "Partial but sufficient",
            },
            "SelfReflectionResult": {
                "quality_score": 0.8,
                "is_hallucination": False,
                "issues": ["partial coverage"],
                "improvement": "",
            },
            "LLMJudgeResult": {
                "is_safe": True,
                "risk_level": "low",
                "reason": "safe",
            },
        },
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)
    state = make_agent_state(question="运费怎么算？", user_id=1)
    result = await agent.process(state)

    assert "运费" in result["response"]
    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["retrieval_adequacy"] == "partial"
    assert self_rag["fallback_triggered"] is False
    assert self_rag["self_reflection_issues"] == ["partial coverage"]


@pytest.mark.asyncio
async def test_self_rag_citation_enforcement(mock_load_config):
    retriever = DeterministicRetriever(
        results=[_Result("退换货政策内容", "policy.md", 0.9)]
    )
    llm = DeterministicChatModel(
        responses=[
            (["政策"], "根据政策，支持7天无理由退货。[来源: policy.md]"),
        ],
        structured={
            "RetrievalAdequacy": {"adequacy": "yes", "confidence": 0.9, "reason": "test"},
            "SelfReflectionResult": {
                "quality_score": 0.9,
                "is_hallucination": False,
                "issues": [],
                "improvement": "",
            },
            "LLMJudgeResult": {
                "is_safe": True,
                "risk_level": "low",
                "reason": "safe",
            },
        },
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)
    state = make_agent_state(question="退货政策是什么？", user_id=1)
    result = await agent.process(state)

    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["citations_verified"] is True
    assert self_rag["citation_count"] == 1


@pytest.mark.asyncio
async def test_self_rag_missing_citations_detected(mock_load_config):
    retriever = DeterministicRetriever(
        results=[_Result("退换货政策内容", "policy.md", 0.9)]
    )
    llm = DeterministicChatModel(
        responses=[
            (["政策"], "根据政策，支持7天无理由退货。"),
        ],
        structured={
            "RetrievalAdequacy": {"adequacy": "yes", "confidence": 0.9, "reason": "test"},
            "SelfReflectionResult": {
                "quality_score": 0.6,
                "is_hallucination": False,
                "issues": ["missing citations"],
                "improvement": "Add citations",
            },
            "LLMJudgeResult": {
                "is_safe": True,
                "risk_level": "low",
                "reason": "safe",
            },
        },
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)
    state = make_agent_state(question="退货政策是什么？", user_id=1)
    result = await agent.process(state)

    self_rag = result["updated_state"]["self_rag"]
    assert self_rag["citations_verified"] is False
    assert self_rag["citation_count"] == 0
    assert "missing citations" in self_rag["self_reflection_issues"]


@pytest.mark.asyncio
async def test_self_rag_result_model():
    result = SelfRAGResult(
        retrieval_adequacy="yes",
        adequacy_confidence=0.9,
        adequacy_reason="Test",
        fallback_triggered=False,
        citations_verified=True,
        citation_count=2,
        self_reflection_score=0.85,
        latency_ms=45.0,
    )
    dumped = result.model_dump()
    assert dumped["retrieval_adequacy"] == "yes"
    assert dumped["adequacy_confidence"] == 0.9
    assert dumped["fallback_triggered"] is False
    assert dumped["latency_ms"] == 45.0


@pytest.fixture
def real_policy_agent(real_llm):
    retriever = DeterministicRetriever(
        results=[
            _Result("退换货政策: 7天无理由退货", "policy.md", 0.9),
            _Result("运费政策: 满100元免运费", "shipping.md", 0.85),
        ]
    )
    return PolicyAgent(retriever=retriever, llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_policy_agent(real_policy_agent, mock_load_config):
    state = make_agent_state(question="怎么退货？", user_id=1)
    result = await real_policy_agent.process(state)
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_policy_agent_shipping(real_policy_agent, mock_load_config):
    state = make_agent_state(question="运费怎么算？", user_id=1)
    result = await real_policy_agent.process(state)
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0
