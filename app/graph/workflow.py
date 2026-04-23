import logging

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    build_account_node,
    build_cart_node,
    build_complaint_node,
    build_decider_node,
    build_evaluator_node,
    build_logistics_node,
    build_memory_node,
    build_order_node,
    build_payment_node,
    build_policy_node,
    build_product_node,
    build_router_node,
    build_supervisor_node,
    build_synthesis_node,
)
from app.graph.subgraphs import build_agent_subgraph
from app.models.state import AgentState

logger = logging.getLogger(__name__)


_COMMON_ALLOWED_KEYS = [
    "question",
    "user_id",
    "thread_id",
    "history",
    "memory_context",
    "memory_context_config",
    "intent_result",
    "slots",
    "iteration_count",
    "experiment_variant_id",
    "variant_llm_model",
    "variant_retriever_top_k",
    "variant_reranker_enabled",
    "context_tokens",
    "context_utilization",
]

_AGENT_ALLOWED_KEYS: dict[str, list[str]] = {
    "policy_agent": [*_COMMON_ALLOWED_KEYS, "retrieval_result"],
    "order_agent": [*_COMMON_ALLOWED_KEYS, "order_data", "retrieval_result"],
    "logistics": [*_COMMON_ALLOWED_KEYS, "order_data", "retrieval_result"],
    "account": [*_COMMON_ALLOWED_KEYS, "retrieval_result"],
    "payment": [*_COMMON_ALLOWED_KEYS, "retrieval_result"],
    "product": [*_COMMON_ALLOWED_KEYS, "product_data", "retrieval_result"],
    "cart": [*_COMMON_ALLOWED_KEYS, "cart_data", "retrieval_result"],
    "complaint": [*_COMMON_ALLOWED_KEYS, "retrieval_result"],
}


def create_workflow(
    router_agent,
    policy_agent,
    order_agent,
    logistics_agent,
    account_agent,
    payment_agent,
    evaluator,
    supervisor_agent=None,
    product_agent=None,
    cart_agent=None,
    complaint_agent=None,
    llm=None,
    structured_manager=None,
    vector_manager=None,
):
    workflow = StateGraph(AgentState)  # type: ignore

    workflow.add_node(
        "router_node",
        build_router_node(router_agent),  # type: ignore
        metadata={"tags": ["router_node", "internal"]},
    )

    if supervisor_agent is not None and llm is not None:
        workflow.add_node(
            "supervisor_node",
            build_supervisor_node(supervisor_agent),  # type: ignore
            metadata={"tags": ["supervisor_node", "internal"]},
        )
        workflow.add_node(
            "synthesis_node",
            build_synthesis_node(llm),  # type: ignore
            metadata={"tags": ["synthesis_node", "internal"]},
        )

    if supervisor_agent is not None:
        workflow.add_node(
            "policy_agent",
            build_agent_subgraph(
                policy_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("policy_agent")
            ),
            metadata={"tags": ["policy_agent", "user_visible"]},
        )
        workflow.add_node(
            "order_agent",
            build_agent_subgraph(order_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("order_agent")),
            metadata={"tags": ["order_agent", "user_visible"]},
        )
        workflow.add_node(
            "logistics",
            build_agent_subgraph(
                logistics_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("logistics")
            ),
            metadata={"tags": ["logistics", "user_visible"]},
        )
        workflow.add_node(
            "account",
            build_agent_subgraph(account_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("account")),
            metadata={"tags": ["account", "user_visible"]},
        )
        workflow.add_node(
            "payment",
            build_agent_subgraph(payment_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("payment")),
            metadata={"tags": ["payment", "user_visible"]},
        )
        if product_agent is not None:
            workflow.add_node(
                "product",
                build_agent_subgraph(
                    product_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("product")
                ),
                metadata={"tags": ["product", "user_visible"]},
            )
        if cart_agent is not None:
            workflow.add_node(
                "cart",
                build_agent_subgraph(cart_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("cart")),
                metadata={"tags": ["cart", "user_visible"]},
            )
        if complaint_agent is not None:
            workflow.add_node(
                "complaint",
                build_agent_subgraph(
                    complaint_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("complaint")
                ),
                metadata={"tags": ["complaint", "user_visible"]},
            )
    else:
        workflow.add_node(
            "policy_agent",
            build_policy_node(policy_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("policy_agent")),  # type: ignore
            metadata={"tags": ["policy_agent", "user_visible"]},
        )
        workflow.add_node(
            "order_agent",
            build_order_node(order_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("order_agent")),  # type: ignore
            metadata={"tags": ["order_agent", "user_visible"]},
        )
        workflow.add_node(
            "logistics",
            build_logistics_node(
                logistics_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("logistics")
            ),  # type: ignore
            metadata={"tags": ["logistics", "user_visible"]},
        )
        workflow.add_node(
            "account",
            build_account_node(account_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("account")),  # type: ignore
            metadata={"tags": ["account", "user_visible"]},
        )
        workflow.add_node(
            "payment",
            build_payment_node(payment_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("payment")),  # type: ignore
            metadata={"tags": ["payment", "user_visible"]},
        )
        if product_agent is not None:
            workflow.add_node(
                "product",
                build_product_node(product_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("product")),  # type: ignore
                metadata={"tags": ["product", "user_visible"]},
            )
        if cart_agent is not None:
            workflow.add_node(
                "cart",
                build_cart_node(cart_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("cart")),  # type: ignore
                metadata={"tags": ["cart", "user_visible"]},
            )
        if complaint_agent is not None:
            workflow.add_node(
                "complaint",
                build_complaint_node(
                    complaint_agent, allowed_keys=_AGENT_ALLOWED_KEYS.get("complaint")
                ),  # type: ignore
                metadata={"tags": ["complaint", "user_visible"]},
            )

    workflow.add_node(
        "memory_node",
        build_memory_node(
            structured_manager,
            vector_manager,
            use_supervisor=supervisor_agent is not None,
        ),  # type: ignore
        metadata={"tags": ["memory_node", "internal"]},
    )
    workflow.add_node(
        "evaluator_node",
        build_evaluator_node(evaluator),  # type: ignore
        metadata={"tags": ["evaluator_node", "confidence_eval", "internal"]},
    )
    workflow.add_node(
        "decider_node",
        build_decider_node(vector_manager),  # type: ignore
        metadata={"tags": ["decider_node", "internal"]},
    )

    workflow.add_edge(START, "router_node")
    workflow.add_edge(
        "policy_agent", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
    )
    workflow.add_edge(
        "order_agent", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
    )
    workflow.add_edge(
        "logistics", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
    )
    workflow.add_edge(
        "account", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
    )
    workflow.add_edge(
        "payment", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
    )

    if product_agent is not None:
        workflow.add_edge(
            "product", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
        )
    if cart_agent is not None:
        workflow.add_edge(
            "cart", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
        )
    if complaint_agent is not None:
        workflow.add_edge(
            "complaint", "synthesis_node" if supervisor_agent is not None else "evaluator_node"
        )

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
    supervisor_agent=None,
    product_agent=None,
    cart_agent=None,
    complaint_agent=None,
    llm=None,
    structured_manager=None,
    vector_manager=None,
):
    logger.info("Compiling LangGraph 1.0+ multi-agent workflow...")

    workflow = create_workflow(
        router_agent,
        policy_agent,
        order_agent,
        logistics_agent,
        account_agent,
        payment_agent,
        evaluator,
        supervisor_agent=supervisor_agent,
        product_agent=product_agent,
        cart_agent=cart_agent,
        complaint_agent=complaint_agent,
        llm=llm,
        structured_manager=structured_manager,
        vector_manager=vector_manager,
    )
    compiled = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled successfully")
    return compiled
