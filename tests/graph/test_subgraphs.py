"""Tests for agent subgraph context isolation."""

import pytest

from app.agents.base import BaseAgent
from app.graph.subgraphs import _filter_state, build_agent_subgraph
from app.models.state import AgentProcessResult, AgentState, make_agent_state
from tests._llm import DeterministicChatModel


class RecordingAgent(BaseAgent):
    """Mock agent that records the state passed to process()."""

    def __init__(self):
        super().__init__(name="recording", llm=DeterministicChatModel())
        self.last_state: AgentState | None = None
        self.process_result: AgentProcessResult = {
            "response": "ok",
            "updated_state": {},
        }

    async def process(self, state: AgentState) -> AgentProcessResult:
        self.last_state = state
        return self.process_result


@pytest.mark.asyncio
async def test_subgraph_filters_state_before_agent_process():
    agent = RecordingAgent()

    allowed_keys = ["question", "user_id", "thread_id", "history"]
    subgraph = build_agent_subgraph(agent, allowed_keys=allowed_keys)

    full_state = make_agent_state(
        question="hello",
        user_id=1,
        thread_id="t1",
        history=[],
        order_data={"status": "shipped"},
        product_data={"name": "iPhone"},
    )

    await subgraph.ainvoke(full_state)

    received_state = agent.last_state
    assert received_state is not None
    assert "question" in received_state
    assert "order_data" not in received_state
    assert "product_data" not in received_state


@pytest.mark.asyncio
async def test_subgraph_without_allowed_keys_passes_full_state():
    agent = RecordingAgent()

    subgraph = build_agent_subgraph(agent)

    full_state = make_agent_state(
        question="hello",
        user_id=1,
        thread_id="t1",
        order_data={"status": "shipped"},
    )

    await subgraph.ainvoke(full_state)

    received_state = agent.last_state
    assert received_state is not None
    assert "order_data" in received_state


@pytest.mark.asyncio
async def test_subgraph_masks_large_updated_state():
    agent = RecordingAgent()
    agent.process_result = {
        "response": "ok",
        "updated_state": {"long_text": "x" * 1000},
    }

    subgraph = build_agent_subgraph(agent, allowed_keys=["question"])
    state = make_agent_state(question="hi")

    result = await subgraph.ainvoke(state)
    sub_answers = result.get("sub_answers", [])
    assert len(sub_answers) == 1
    updated = sub_answers[0]["updated_state"]
    assert updated.get("long_text", {}).get("_masked") is True


def test_filter_state_retains_only_allowed_keys():
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="t1",
        order_data={"status": "shipped"},
    )
    filtered = _filter_state(state, ["question", "user_id"])
    assert set(filtered.keys()) == {"question", "user_id"}
