from unittest.mock import patch

import pytest

from app.agents.base import BaseAgent
from app.models.experiment import Experiment, ExperimentStatus, ExperimentVariant
from app.models.state import AgentState, make_agent_state
from tests._llm import DeterministicChatModel


class DummyAgent(BaseAgent):
    async def process(self, state: AgentState):
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        return {"response": self._dynamic_system_prompt or "no override", "updated_state": {}}


@pytest.mark.asyncio
async def test_resolve_experiment_prompt_returns_variant_system_prompt(db_session):
    exp = Experiment(name="test_prompt_exp", status=ExperimentStatus.RUNNING.value)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.id is not None

    variant = ExperimentVariant(
        experiment_id=exp.id,
        name="treatment",
        weight=1,
        system_prompt="override prompt from variant",
    )
    db_session.add(variant)
    await db_session.flush()
    await db_session.refresh(variant)
    assert variant.id is not None

    agent = DummyAgent(name="test_agent", llm=DeterministicChatModel(), system_prompt="base prompt")
    state = make_agent_state(
        question="hello", user_id=1, thread_id="t1", experiment_variant_id=variant.id
    )

    with patch("app.core.database.async_session_maker") as mock_maker:

        async def _context_manager(*_args, **_kwargs):
            return db_session

        mock_maker.return_value.__aenter__ = _context_manager

        async def _aexit(*_args, **_kwargs):
            return True

        mock_maker.return_value.__aexit__ = _aexit
        result = await agent.process(state)

    assert result["response"] == "override prompt from variant"


@pytest.mark.asyncio
async def test_resolve_experiment_prompt_returns_none_for_missing_variant():
    agent = DummyAgent(name="test_agent", llm=DeterministicChatModel(), system_prompt="base prompt")
    state = make_agent_state(
        question="hello", user_id=1, thread_id="t1", experiment_variant_id=999999
    )
    override = await agent._resolve_experiment_prompt(state)
    assert override is None


@pytest.mark.asyncio
async def test_resolve_experiment_prompt_no_variant_id():
    agent = DummyAgent(name="test_agent", llm=DeterministicChatModel(), system_prompt="base prompt")
    state = make_agent_state(question="hello", user_id=1, thread_id="t1")
    override = await agent._resolve_experiment_prompt(state)
    assert override is None
