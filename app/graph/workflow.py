import logging

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    build_account_node,
    build_evaluator_node,
    build_logistics_node,
    build_order_node,
    build_payment_node,
    build_policy_node,
    build_router_node,
    decider_node,
)
from app.models.state import AgentState

logger = logging.getLogger(__name__)


def create_workflow(
    router_agent,
    policy_agent,
    order_agent,
    logistics_agent,
    account_agent,
    payment_agent,
    evaluator,
):
    workflow = StateGraph(AgentState)  # type: ignore

    workflow.add_node(
        "router_node",
        build_router_node(router_agent),  # type: ignore
        metadata={"tags": ["router_node", "internal"]},
    )
    workflow.add_node(
        "policy_agent",
        build_policy_node(policy_agent),  # type: ignore
        metadata={"tags": ["policy_agent", "user_visible"]},
    )
    workflow.add_node(
        "order_agent",
        build_order_node(order_agent),  # type: ignore
        metadata={"tags": ["order_agent", "user_visible"]},
    )
    workflow.add_node(
        "logistics",
        build_logistics_node(logistics_agent),  # type: ignore
        metadata={"tags": ["logistics", "user_visible"]},
    )
    workflow.add_node(
        "account",
        build_account_node(account_agent),  # type: ignore
        metadata={"tags": ["account", "user_visible"]},
    )
    workflow.add_node(
        "payment",
        build_payment_node(payment_agent),  # type: ignore
        metadata={"tags": ["payment", "user_visible"]},
    )
    workflow.add_node(
        "evaluator_node",
        build_evaluator_node(evaluator),  # type: ignore
        metadata={"tags": ["evaluator_node", "confidence_eval", "internal"]},
    )
    workflow.add_node(
        "decider_node",
        decider_node,
        metadata={"tags": ["decider_node", "internal"]},
    )

    workflow.add_edge(START, "router_node")
    workflow.add_edge("policy_agent", "evaluator_node")
    workflow.add_edge("order_agent", "evaluator_node")
    workflow.add_edge("logistics", "evaluator_node")
    workflow.add_edge("account", "evaluator_node")
    workflow.add_edge("payment", "evaluator_node")
    workflow.add_edge("evaluator_node", "decider_node")
    workflow.add_edge("decider_node", END)

    return workflow


async def compile_app_graph(
    router_agent,
    policy_agent,
    order_agent,
    logistics_agent,
    account_agent,
    payment_agent,
    evaluator,
    checkpointer,
):
    """编译 LangGraph（1.0+）"""
    logger.info("Compiling LangGraph 1.0+ multi-agent workflow...")

    workflow = create_workflow(
        router_agent,
        policy_agent,
        order_agent,
        logistics_agent,
        account_agent,
        payment_agent,
        evaluator,
    )
    compiled = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled successfully")
    return compiled
