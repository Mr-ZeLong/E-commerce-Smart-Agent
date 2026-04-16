# app/models/state.py
import operator
from typing import Annotated, Any, NotRequired, TypedDict


class AgentProcessResult(TypedDict):
    """Agent.process() 的统一返回类型"""

    response: str
    updated_state: NotRequired[dict[str, Any]]


class AgentState(TypedDict):
    """Agent 状态定义"""

    question: str
    user_id: int
    thread_id: str

    current_agent: str | None
    next_agent: str | None
    iteration_count: int
    retry_requested: bool

    history: Annotated[list[dict], operator.add]

    retrieval_result: dict[str, Any] | None

    order_data: dict | None

    audit_level: str | None
    audit_log_id: int | None
    audit_reason: str | None

    confidence_score: float | None
    confidence_signals: dict | None

    needs_human_transfer: bool
    transfer_reason: str | None

    messages: Annotated[list[dict[str, Any]], operator.add]
    answer: str

    refund_flow_active: bool | None
    refund_order_sn: str | None
    refund_step: str | None

    # Intent & clarification fields produced by the graph
    intent_result: dict[str, Any] | None
    slots: dict[str, Any] | None
    awaiting_clarification: bool | None
    clarification_state: dict[str, Any] | None
    refund_data: dict[str, Any] | None

    execution_mode: str | None
    sub_answers: Annotated[list[dict[str, Any]], operator.add]
    supervisor_reasoning: str | None
    synthesized_answer: str | None
    pending_agent_results: list[str] | None
    completed_agents: list[str] | None
    product_data: dict[str, Any] | None
    cart_data: dict[str, Any] | None
    memory_context: dict[str, Any] | None
    experiment_variant_id: int | None


def make_agent_state(
    *,
    question: str,
    user_id: int = 1,
    thread_id: str = "default",
    current_agent: str | None = None,
    next_agent: str | None = None,
    iteration_count: int = 0,
    retry_requested: bool = False,
    history: list[dict] | None = None,
    retrieval_result: dict[str, Any] | None = None,
    order_data: dict | None = None,
    audit_level: str | None = None,
    audit_log_id: int | None = None,
    audit_reason: str | None = None,
    confidence_score: float | None = None,
    confidence_signals: dict | None = None,
    needs_human_transfer: bool = False,
    transfer_reason: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    answer: str = "",
    refund_flow_active: bool | None = None,
    refund_order_sn: str | None = None,
    refund_step: str | None = None,
    intent_result: dict[str, Any] | None = None,
    slots: dict[str, Any] | None = None,
    awaiting_clarification: bool | None = None,
    clarification_state: dict[str, Any] | None = None,
    refund_data: dict[str, Any] | None = None,
    execution_mode: str | None = None,
    sub_answers: list[dict[str, Any]] | None = None,
    supervisor_reasoning: str | None = None,
    synthesized_answer: str | None = None,
    pending_agent_results: list[str] | None = None,
    completed_agents: list[str] | None = None,
    product_data: dict[str, Any] | None = None,
    cart_data: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
    experiment_variant_id: int | None = None,
) -> AgentState:
    return {
        "question": question,
        "user_id": user_id,
        "thread_id": thread_id,
        "history": history if history is not None else [],
        "current_agent": current_agent,
        "next_agent": next_agent,
        "iteration_count": iteration_count,
        "retry_requested": retry_requested,
        "retrieval_result": retrieval_result,
        "order_data": order_data,
        "audit_level": audit_level,
        "audit_log_id": audit_log_id,
        "audit_reason": audit_reason,
        "confidence_score": confidence_score,
        "confidence_signals": confidence_signals,
        "messages": messages if messages is not None else [],
        "answer": answer,
        "refund_flow_active": refund_flow_active,
        "refund_order_sn": refund_order_sn,
        "refund_step": refund_step,
        "needs_human_transfer": needs_human_transfer,
        "transfer_reason": transfer_reason,
        "intent_result": intent_result,
        "slots": slots,
        "awaiting_clarification": awaiting_clarification,
        "clarification_state": clarification_state,
        "refund_data": refund_data,
        "execution_mode": execution_mode,
        "sub_answers": sub_answers if sub_answers is not None else [],
        "supervisor_reasoning": supervisor_reasoning,
        "synthesized_answer": synthesized_answer,
        "pending_agent_results": pending_agent_results,
        "completed_agents": completed_agents,
        "product_data": product_data,
        "cart_data": cart_data,
        "memory_context": memory_context,
        "experiment_variant_id": experiment_variant_id,
    }
