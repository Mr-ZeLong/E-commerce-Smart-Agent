import pytest

from app.agents.policy import POLICY_SYSTEM_PROMPT, PolicyAgent
from app.models.state import make_agent_state
from tests._agents import DeterministicRetriever
from tests._llm import DeterministicChatModel


def test_policy_system_prompt_requires_citation():
    assert "[来源:" in POLICY_SYSTEM_PROMPT


class _Result:
    def __init__(self, content, source, score):
        self.content = content
        self.source = source
        self.score = score


@pytest.mark.asyncio
async def test_policy_agent_uses_retriever():
    results = [_Result("退换货政策内容", "policy.md", 0.95)]
    retriever = DeterministicRetriever(results=results)
    agent = PolicyAgent(retriever=retriever, llm=DeterministicChatModel())

    state = make_agent_state(question="怎么退货")
    chunks, sims, sources = await agent._retrieve_knowledge(state)
    assert chunks == ["退换货政策内容"]
    assert sims == [pytest.approx(0.95)]
    assert sources == ["policy.md"]


@pytest.mark.asyncio
async def test_process_with_rag_context():
    retriever = DeterministicRetriever(
        results=[
            _Result("运费满100免运费", "policy_doc_1", 0.8),
            _Result("配送时效1-3天", "policy_doc_2", 0.75),
        ]
    )
    llm = DeterministicChatModel(
        responses=[
            (["运费", "配送", "政策"], "运费满100元免运费，配送时效为1-3天。"),
        ]
    )
    agent = PolicyAgent(retriever=retriever, llm=llm)

    state = make_agent_state(question="运费怎么算？", user_id=1)
    result = await agent.process(state)

    assert "运费" in result["response"]
    assert result["updated_state"]["retrieval_result"]["chunks"] == [
        "运费满100免运费",
        "配送时效1-3天",
    ]


@pytest.mark.asyncio
async def test_process_with_empty_retrieval():
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


@pytest.mark.asyncio
async def test_retrieve_knowledge_filters_low_score_chunks():
    class LowScoreRetriever(DeterministicRetriever):
        async def retrieve(self, query, conversation_history=None, memory_context=None):
            return [
                _Result("高相关", "doc1", 0.6),
                _Result("低相关", "doc2", 0.3),
                _Result("刚好相关", "doc3", 0.5),
            ]

    agent = PolicyAgent(retriever=LowScoreRetriever(), llm=DeterministicChatModel())
    state = make_agent_state(question="运费政策", user_id=1)
    chunks, sims, sources = await agent._retrieve_knowledge(state)
    assert "低相关" not in chunks
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_retrieve_knowledge_returns_empty_when_grader_rejects_all():
    class OneResultRetriever(DeterministicRetriever):
        async def retrieve(self, query, conversation_history=None, memory_context=None):
            return [_Result("某个文档", "doc1", 0.8)]

    llm = DeterministicChatModel(structured={"GradeDocuments": {"binary_score": "no"}})
    agent = PolicyAgent(retriever=OneResultRetriever(), llm=llm)
    state = make_agent_state(question="退换货", user_id=1)
    chunks, sims, sources = await agent._retrieve_knowledge(state)
    assert chunks == []


@pytest.mark.asyncio
async def test_process_self_rag_refusal_when_no_relevant_docs():
    class OneResultRetriever(DeterministicRetriever):
        async def retrieve(self, query, conversation_history=None, memory_context=None):
            return [_Result("不相关文档", "doc1", 0.8)]

    llm = DeterministicChatModel(structured={"GradeDocuments": {"binary_score": "no"}})
    agent = PolicyAgent(retriever=OneResultRetriever(), llm=llm)
    state = make_agent_state(question="运费政策", user_id=1)
    result = await agent.process(state)
    assert "抱歉" in result["response"] or "暂未查询" in result["response"]


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
async def test_real_llm_policy_agent(real_policy_agent):
    state = make_agent_state(question="怎么退货？", user_id=1)
    result = await real_policy_agent.process(state)
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_policy_agent_shipping(real_policy_agent):
    state = make_agent_state(question="运费怎么算？", user_id=1)
    result = await real_policy_agent.process(state)
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0
