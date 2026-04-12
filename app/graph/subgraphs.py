from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.models.state import AgentState


def build_agent_subgraph(agent: BaseAgent):
    workflow = StateGraph(AgentState)  # type: ignore

    async def agent_node(state: AgentState) -> dict:
        result = await agent.process(state)
        return {
            "sub_answers": [
                {
                    "agent": agent.name,
                    "response": result.get("response", ""),
                    "updated_state": result.get("updated_state") or {},
                    "iteration": state.get("iteration_count", 0),
                }
            ],
        }

    workflow.add_node("agent", agent_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)

    return workflow.compile()
