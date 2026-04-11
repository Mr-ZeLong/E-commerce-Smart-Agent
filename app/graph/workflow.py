import logging

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.graph.nodes import (
    build_evaluator_node,
    build_order_node,
    build_policy_node,
    build_router_node,
    decider_node,
)
from app.models.state import AgentState

logger = logging.getLogger(__name__)


def create_workflow(router_agent, policy_agent, order_agent, evaluator):
    # LangGraph type stubs don't fully support TypedDict state schemas.
    workflow = StateGraph(AgentState)  # type: ignore

    workflow.add_node("router_node", build_router_node(router_agent))
    workflow.add_node("policy_agent", build_policy_node(policy_agent))
    workflow.add_node("order_agent", build_order_node(order_agent))
    workflow.add_node("evaluator_node", build_evaluator_node(evaluator))
    workflow.add_node("decider_node", decider_node)

    workflow.add_edge(START, "router_node")
    workflow.add_edge("policy_agent", "evaluator_node")
    workflow.add_edge("order_agent", "evaluator_node")
    workflow.add_edge("evaluator_node", "decider_node")
    workflow.add_edge("decider_node", END)

    return workflow


async def compile_app_graph(router_agent, policy_agent, order_agent, evaluator):
    """编译 LangGraph（1.0+）"""
    logger.info("Compiling LangGraph 1.0+ multi-agent workflow...")

    checkpointer = AsyncRedisSaver(redis_url=settings.REDIS_URL)
    await checkpointer.setup()

    workflow = create_workflow(router_agent, policy_agent, order_agent, evaluator)
    compiled = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled successfully")
    return compiled
