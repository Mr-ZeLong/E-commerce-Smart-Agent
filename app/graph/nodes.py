"""LangGraph 1.0+ 节点函数

原 SupervisorAgent 和 AgentOrchestrator 的逻辑已直接下沉到这些节点中。
业务逻辑层（PolicyAgent/OrderAgent 等）保持不变。
"""
import logging
from typing import Any, Literal, cast

from langgraph.types import Command

from app.agents.base import AgentResult
from app.agents.evaluator import ConfidenceEvaluator
from app.agents.order import OrderAgent
from app.agents.policy import PolicyAgent
from app.agents.router import IntentRouterAgent
from app.core.config import settings
from app.models.state import AgentState

logger = logging.getLogger(__name__)

_router_agent: IntentRouterAgent | None = None
_policy_agent: PolicyAgent | None = None
_order_agent: OrderAgent | None = None


def _get_router_agent() -> IntentRouterAgent:
    global _router_agent
    if _router_agent is None:
        _router_agent = IntentRouterAgent()
    return _router_agent


def _get_policy_agent() -> PolicyAgent:
    global _policy_agent
    if _policy_agent is None:
        _policy_agent = PolicyAgent()
    return _policy_agent


def _get_order_agent() -> OrderAgent:
    global _order_agent
    if _order_agent is None:
        _order_agent = OrderAgent()
    return _order_agent


async def router_node(state: AgentState) -> Command[Literal["policy_agent", "order_agent", "decider_node"]]:
    """意图识别与路由节点（原 Supervisor + Orchestrator 的路由部分）"""
    router = _get_router_agent()
    router_result = await router.process(cast(dict[str, Any], state))
    updated = dict(router_result.updated_state or {})
    iteration = state.get("iteration_count", 0) + 1
    updated["iteration_count"] = iteration

    # 直接回复场景（闲聊、问候、澄清）
    if router_result.response:
        return Command(
            goto="decider_node",
            update={"answer": router_result.response, **updated}
        )

    if state.get("retry_requested"):
        # 如果重试后仍然要路由到同一个 specialist，直接转人工
        next_agent = updated.get("next_agent")
        current_agent = state.get("current_agent")
        if next_agent and current_agent and (
            (next_agent == "policy" and current_agent == "policy_agent") or
            (next_agent == "order" and current_agent == "order_agent") or
            (next_agent == "supervisor" and current_agent == "policy_agent")
        ):
            return Command(
                goto="decider_node",
                update={
                    "answer": router_result.response or "系统对该问题没有足够把握，已为您转接人工客服。",
                    "needs_human_transfer": True,
                    "transfer_reason": "confidence_retry_routed_to_same_agent",
                    **updated,
                }
            )
        # 否则清除 retry_requested 继续正常路由
        updated["retry_requested"] = False

    next_agent = updated.get("next_agent")
    if not next_agent:
        return Command(
            goto="decider_node",
            update={
                "answer": "无法确定处理该请求的专业代理，请尝试换一种方式描述您的问题。",
                "needs_human_transfer": True,
                **updated,
            }
        )

    if iteration > settings.MAX_ROUTER_ITERATIONS:
        logger.warning("Router 迭代次数超过限制: %s", iteration)
        return Command(
            goto="decider_node",
            update={
                "answer": "系统处理步数过多，请联系人工客服。",
                "needs_human_transfer": True,
            }
        )

    if next_agent == "policy" or next_agent == "supervisor":
        return Command(goto="policy_agent", update=updated)
    elif next_agent == "order":
        return Command(goto="order_agent", update=updated)
    else:
        return Command(
            goto="decider_node",
            update={"answer": router_result.response or "暂不支持该类型请求", **updated}
        )


async def policy_node(state: AgentState) -> Command[Literal["evaluator_node"]]:
    """Policy Specialist 节点"""
    agent = _get_policy_agent()
    result = await agent.process(cast(dict[str, Any], state))
    updates = _build_updates(result)
    updates["current_agent"] = "policy_agent"
    return Command(goto="evaluator_node", update=updates)


async def order_node(state: AgentState) -> Command[Literal["evaluator_node"]]:
    """Order Specialist 节点"""
    agent = _get_order_agent()
    result = await agent.process(cast(dict[str, Any], state))
    updates = _build_updates(result)
    updates["current_agent"] = "order_agent"
    return Command(goto="evaluator_node", update=updates)


def _build_updates(result: AgentResult) -> dict[str, Any]:
    """从 AgentResult 构建状态更新"""
    updates: dict[str, Any] = {"answer": result.response}
    if result.updated_state:
        updates.update(result.updated_state)
    if result.needs_human:
        updates["needs_human_transfer"] = True
        updates["transfer_reason"] = result.transfer_reason
    return updates


async def evaluator_node(state: AgentState) -> Command[Literal["decider_node", "router_node"]]:
    """置信度评估节点"""
    if state.get("needs_human_transfer"):
        return Command(goto="decider_node", update={})

    evaluator = ConfidenceEvaluator()
    eval_result = await evaluator.evaluate(
        answer=state.get("answer", ""),
        question=state.get("question", ""),
        history=state.get("history", []),
        retrieval_result=state.get("retrieval_result"),
    )

    # 极低置信度且未超限，返回 router 重试一次
    if eval_result.get("confidence_score", 0) < settings.CONFIDENCE_RETRY_THRESHOLD and state.get("iteration_count", 0) <= 3:
        return Command(
            goto="router_node",
            update={"retry_requested": True, **eval_result}
        )

    return Command(goto="decider_node", update=eval_result)


def decider_node(state: AgentState) -> dict:
    """转人工最终决策节点"""
    specialist_result = AgentResult(
        response=state.get("answer", ""),
        updated_state=dict(state),
        confidence=state.get("confidence_score"),
        needs_human=state.get("needs_human_transfer", False),
        transfer_reason=state.get("transfer_reason"),
    )

    if specialist_result.needs_human:
        final_state = {
            "answer": specialist_result.response,
            "confidence_score": specialist_result.confidence or 0.0,
            "confidence_signals": {},
            "needs_human_transfer": True,
            "transfer_reason": specialist_result.transfer_reason or "specialist_requested_transfer",
            "audit_level": "manual",
        }
    elif state.get("confidence_score") is not None:
        final_state = dict(state)
    else:
        final_state = {
            "answer": specialist_result.response,
            "confidence_score": 0.0,
            "confidence_signals": {},
            "needs_human_transfer": True,
            "transfer_reason": "missing_evaluation",
            "audit_level": "manual",
        }

    # 合并 Specialist 返回的状态更新（但不覆盖关键字段和内部字段）
    if specialist_result.updated_state:
        for key, value in specialist_result.updated_state.items():
            if key not in final_state and not key.startswith("_"):
                final_state[key] = value

    return {
        "answer": state.get("answer", ""),
        "needs_human_transfer": final_state.get("needs_human_transfer", False),
        "transfer_reason": final_state.get("transfer_reason"),
        "audit_level": final_state.get("audit_level"),
        "confidence_score": state.get("confidence_score"),
        "confidence_signals": state.get("confidence_signals"),
        "intent": state.get("intent"),
    }
