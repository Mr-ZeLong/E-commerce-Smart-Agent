import json
import logging
from typing import cast

from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.context.masking import mask_observation
from app.models.state import AgentState
from app.observability.metrics import (
    record_agent_context_reduction,
    record_agent_context_tokens,
)

logger = logging.getLogger(__name__)


def _filter_state(state: AgentState, allowed_keys: list[str]) -> AgentState:
    """Return a copy of ``state`` containing only ``allowed_keys``."""
    return cast(AgentState, {k: v for k, v in state.items() if k in allowed_keys})


def _estimate_state_tokens(state: AgentState) -> int:
    """Estimate token count for a serialized state dictionary."""
    try:
        import tiktoken

        encoder = tiktoken.get_encoding("cl100k_base")
        serialized = json.dumps(state, ensure_ascii=False, default=str)
        return len(encoder.encode(serialized))
    except (ImportError, OSError):
        serialized = json.dumps(state, ensure_ascii=False, default=str)
        return len(serialized) // 4


def get_agent_tools(agent_name: str) -> list[dict[str, str]]:
    """Return tool definitions scoped to ``agent_name``.

    Args:
        agent_name: Name of the expert agent.

    Returns:
        List of tool metadata dicts with ``name`` and ``description`` keys.
    """
    from app.graph.workflow import get_agent_tool_scope

    tool_names = get_agent_tool_scope(agent_name)
    return [{"name": name, "description": f"Tool '{name}' for {agent_name}"} for name in tool_names]


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
        full_tokens = _estimate_state_tokens(state)
        isolated_state = _filter_state(state, allowed_keys) if allowed_keys else state
        filtered_tokens = _estimate_state_tokens(isolated_state)
        reduction_pct = (
            round(((full_tokens - filtered_tokens) / full_tokens) * 100, 2)
            if full_tokens > 0
            else 0.0
        )
        logger.info(
            "[ContextIsolation] agent=%s full_tokens=%s filtered_tokens=%s reduction=%s%%",
            agent.name,
            full_tokens,
            filtered_tokens,
            reduction_pct,
        )
        record_agent_context_tokens(tokens=filtered_tokens, agent_name=agent.name)
        if full_tokens > 0:
            reduction_ratio = (full_tokens - filtered_tokens) / full_tokens
            record_agent_context_reduction(agent_name=agent.name, ratio=round(reduction_ratio, 4))

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
