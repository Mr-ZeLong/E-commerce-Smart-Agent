"""LangGraph 1.0+ 节点函数"""

import logging
from typing import Any, Literal

from langgraph.types import Command

from app.agents.evaluator import ConfidenceEvaluator
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.router import IntentRouterAgent
from app.core.config import settings
from app.models.state import AgentState

logger = logging.getLogger(__name__)

router_agent = IntentRouterAgent()
policy_agent = PolicyAgent()
order_agent = OrderAgent()
evaluator = ConfidenceEvaluator()


async def router_node(
    state: AgentState,
) -> Command[Literal["policy_agent", "order_agent", "decider_node"]]:
    """意图识别与路由节点"""
    result = await router_agent.process(state)
    updated = dict(result.get("updated_state") or {})

    if result.get("response"):
        return Command(goto="decider_node", update={"answer": result["response"], **updated})

    next_agent = updated.get("next_agent")
    if next_agent == "policy" or next_agent == "supervisor":
        return Command(goto="policy_agent", update=updated)
    elif next_agent == "order":
        return Command(goto="order_agent", update=updated)
    else:
        return Command(
            goto="decider_node",
            update={"answer": result.get("response") or "暂不支持该类型请求", **updated},
        )


async def policy_node(state: AgentState) -> Command[Literal["evaluator_node"]]:
    result = await policy_agent.process(state)
    updates: dict[str, Any] = {"answer": result.get("response", "")}
    if result.get("updated_state"):
        updates.update(result["updated_state"])
    updates["current_agent"] = "policy_agent"
    return Command(goto="evaluator_node", update=updates)


async def order_node(state: AgentState) -> Command[Literal["evaluator_node"]]:
    result = await order_agent.process(state)
    updates: dict[str, Any] = {"answer": result.get("response", "")}
    if result.get("updated_state"):
        updates.update(result["updated_state"])
    updates["current_agent"] = "order_agent"
    return Command(goto="evaluator_node", update=updates)


async def evaluator_node(state: AgentState) -> Command[Literal["decider_node", "router_node"]]:
    if state.get("needs_human_transfer"):
        return Command(goto="decider_node", update={})

    eval_result = await evaluator.evaluate(
        answer=state.get("answer", ""),
        question=state.get("question", ""),
        history=state.get("history", []),
        retrieval_result=state.get("retrieval_result"),
    )

    if (
        eval_result.get("confidence_score", 0) < settings.CONFIDENCE_RETRY_THRESHOLD
        and state.get("iteration_count", 0) <= settings.MAX_EVALUATOR_RETRIES
    ):
        return Command(goto="router_node", update={"retry_requested": True, **eval_result})

    return Command(goto="decider_node", update=eval_result)


def decider_node(state: AgentState) -> dict:
    """转人工最终决策节点"""
    if state.get("needs_human_transfer"):
        return {
            "answer": state.get("answer", ""),
            "confidence_score": state.get("confidence_score") or 0.0,
            "confidence_signals": {},
            "needs_human_transfer": True,
            "transfer_reason": state.get("transfer_reason") or "specialist_requested_transfer",
            "audit_level": "manual",
        }

    if state.get("confidence_score") is not None:
        return {
            "answer": state.get("answer", ""),
            "needs_human_transfer": False,
            "transfer_reason": state.get("transfer_reason"),
            "audit_level": state.get("audit_level"),
            "confidence_score": state.get("confidence_score"),
            "confidence_signals": state.get("confidence_signals"),
        }

    return {
        "answer": state.get("answer", ""),
        "confidence_score": 0.0,
        "confidence_signals": {},
        "needs_human_transfer": True,
        "transfer_reason": "missing_evaluation",
        "audit_level": "manual",
    }
