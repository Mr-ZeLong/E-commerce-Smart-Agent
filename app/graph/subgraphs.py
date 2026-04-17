from typing import cast

from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.context.masking import mask_observation
from app.models.state import AgentState


def _filter_state(state: AgentState, allowed_keys: list[str]) -> AgentState:
    """Return a copy of ``state`` containing only ``allowed_keys``."""
    return cast(AgentState, {k: v for k, v in state.items() if k in allowed_keys})


def build_agent_subgraph(agent: BaseAgent, allowed_keys: list[str] | None = None):
    """Build an isolated subgraph for ``agent``.

    Args:
        agent: The expert agent to wrap.
        allowed_keys: Optional list of state keys the agent is allowed to see.
            When provided, the full ``AgentState`` is filtered before being
            passed to ``agent.process()``. Isolation happens at the subgraph
            boundary so agents cannot access data produced by other experts.
    """
    workflow = StateGraph(AgentState)  # type: ignore

    async def agent_node(state: AgentState) -> dict:
        isolated_state = _filter_state(state, allowed_keys) if allowed_keys else state
        result = await agent.process(isolated_state)
        updated_state = result.get("updated_state") or {}
        if updated_state:
            updated_state = mask_observation(updated_state)
        return {
            "current_agent": agent.name,
            "sub_answers": [
                {
                    "agent": agent.name,
                    "response": result.get("response", ""),
                    "updated_state": updated_state,
                    "iteration": state.get("iteration_count", 0),
                }
            ],
        }

    workflow.add_node("agent", agent_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)

    return workflow.compile()
