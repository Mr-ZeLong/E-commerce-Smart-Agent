import pytest

from app.agents.policy import PolicyAgent
from app.models.state import make_agent_state
from tests._agents import DeterministicRetriever
from tests._llm import DeterministicChatModel


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
