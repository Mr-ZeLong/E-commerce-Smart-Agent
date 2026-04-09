from unittest.mock import AsyncMock, patch

import pytest

from app.agents.policy import PolicyAgent


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
