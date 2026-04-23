import pytest

from app.graph.workflow import (
    _AGENT_ALLOWED_KEYS,
    create_workflow,
    get_agent_tool_scope,
)
from tests._agents import DeterministicAgent


@pytest.mark.asyncio
async def test_workflow_compiles(redis_checkpointer):
    checkpointer = redis_checkpointer
    app_graph = create_workflow(
        router_agent=DeterministicAgent(),
        policy_agent=DeterministicAgent(),
        order_agent=DeterministicAgent(),
        logistics_agent=DeterministicAgent(),
        account_agent=DeterministicAgent(),
        payment_agent=DeterministicAgent(),
        evaluator=DeterministicAgent(),
        supervisor_agent=DeterministicAgent(),
        product_agent=DeterministicAgent(),
        cart_agent=DeterministicAgent(),
        llm=DeterministicAgent(),
    ).compile(checkpointer=checkpointer)
    assert app_graph is not None


def test_agent_allowed_keys_are_granular():
    assert "order_agent" in _AGENT_ALLOWED_KEYS
    order_keys = _AGENT_ALLOWED_KEYS["order_agent"]
    assert "order_data" in order_keys
    assert "retrieval_result" in order_keys
    assert "refund_data" in order_keys
    assert "audit_level" in order_keys


def test_agent_allowed_keys_differ_by_agent():
    order_keys = set(_AGENT_ALLOWED_KEYS["order_agent"])
    product_keys = set(_AGENT_ALLOWED_KEYS["product"])
    assert "order_data" in order_keys
    assert "order_data" not in product_keys
    assert "product_data" in product_keys
    assert "product_data" not in order_keys


def test_get_agent_tool_scope_returns_tools():
    order_tools = get_agent_tool_scope("order_agent")
    assert len(order_tools) > 0
    assert "get_order" in order_tools


def test_get_agent_tool_scope_returns_empty_for_unknown():
    assert get_agent_tool_scope("unknown_agent") == []
