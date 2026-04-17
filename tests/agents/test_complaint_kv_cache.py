"""Tests for KV-Cache optimization in ComplaintAgent."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.complaint import ComplaintAgent
from app.models.state import make_agent_state
from tests._llm import DeterministicChatModel


@pytest.mark.asyncio
async def test_complaint_agent_few_shot_in_user_message():
    agent = ComplaintAgent(llm=DeterministicChatModel())
    agent._few_shot_examples = [
        {"query": "投诉质量", "response": "已记录"},
    ]

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt",
            new=AsyncMock(return_value=None),
        ),
        patch.object(agent._tool, "create_ticket", new=AsyncMock(return_value={"ticket_id": 1})),
    ):
        state = make_agent_state(question="我要投诉")
        result = await agent.process(state)

    assert result["response"] is not None
