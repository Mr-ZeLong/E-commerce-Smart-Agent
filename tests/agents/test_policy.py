from unittest.mock import AsyncMock, patch

import pytest

from app.agents.policy import PolicyAgent
from app.models.state import make_agent_state


@pytest.mark.asyncio
async def test_policy_agent_uses_retriever():
    agent = PolicyAgent()
    mock_result = [
        type("C", (), {"content": "退换货政策内容", "source": "policy.md", "score": 0.95})(),
    ]

    with patch("app.agents.policy.get_retriever") as mock_factory:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = mock_result
        mock_factory.return_value = mock_retriever

        chunks, sims, sources = await agent._retrieve_knowledge("怎么退货")
        assert chunks == ["退换货政策内容"]
        assert sims == [pytest.approx(0.95)]
        assert sources == ["policy.md"]


@pytest.mark.asyncio
async def test_process_with_rag_context():
    policy_agent = PolicyAgent()
    with patch.object(policy_agent, "_retrieve_knowledge", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = (
            ["运费满100免运费", "配送时效1-3天"],
            [0.8, 0.75],
            ["policy_doc_1", "policy_doc_2"],
        )

        with patch.object(policy_agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "运费满100元免运费，配送时效为1-3天。"

            state = make_agent_state(question="运费怎么算？", user_id=1)
            result = await policy_agent.process(state)

            assert "运费" in result["response"]
            assert result["updated_state"]["retrieval_result"]["chunks"] == [
                "运费满100免运费",
                "配送时效1-3天",
            ]


@pytest.mark.asyncio
async def test_process_with_empty_retrieval():
    policy_agent = PolicyAgent()
    with patch.object(policy_agent, "_retrieve_knowledge", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = ([], [], [])

        with patch.object(policy_agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "抱歉，暂未查询到相关规定"

            state = make_agent_state(question="请问这个政策是什么意思？", user_id=1)
            result = await policy_agent.process(state)

            assert "抱歉" in result["response"] or "暂未查询" in result["response"]
