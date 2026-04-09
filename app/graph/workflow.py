import logging

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.graph.nodes import (
    decider_node,
    evaluator_node,
    order_node,
    policy_node,
    router_node,
)
from app.models.state import AgentState

logger = logging.getLogger(__name__)

workflow = StateGraph(AgentState)  # type: ignore

workflow.add_node("router_node", router_node)
workflow.add_node("policy_agent", policy_node)
workflow.add_node("order_agent", order_node)
workflow.add_node("evaluator_node", evaluator_node)
workflow.add_node("decider_node", decider_node)

workflow.add_edge(START, "router_node")
workflow.add_edge("policy_agent", "evaluator_node")
workflow.add_edge("order_agent", "evaluator_node")
workflow.add_edge("evaluator_node", "decider_node")
workflow.add_edge("decider_node", END)

app_graph = None


async def compile_app_graph():
    """编译 LangGraph（1.0+）"""
    global app_graph
    logger.info("Compiling LangGraph 1.0+ multi-agent workflow...")

    checkpointer = AsyncRedisSaver(redis_url=settings.REDIS_URL)
    await checkpointer.setup()

    app_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled successfully")
    return app_graph
