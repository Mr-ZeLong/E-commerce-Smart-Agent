from langgraph.types import Send

from app.intent.multi_intent import are_independent
from app.models.state import AgentState


def plan_dispatch(
    agent_queue: list[str], intent_queue: list[str], completed: list[str]
) -> tuple[str, list[str]]:
    completed_set = set(completed)
    remaining = [
        (intent, agent)
        for intent, agent in zip(intent_queue, agent_queue, strict=True)
        if agent not in completed_set
    ]

    if not remaining:
        return "done", []

    all_independent = True
    for i in range(len(remaining)):
        for j in range(i + 1, len(remaining)):
            if not are_independent(remaining[i][0], remaining[j][0]):
                all_independent = False
                break
        if not all_independent:
            break

    if all_independent and len(remaining) > 1:
        return "parallel", [agent for _, agent in remaining]

    return "serial", [remaining[0][1]]


def build_parallel_sends(agent_names: list[str], state: AgentState) -> list[Send]:
    return [Send(name, {}) for name in agent_names]
