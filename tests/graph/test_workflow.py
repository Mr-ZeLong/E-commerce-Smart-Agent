import pytest

from app.graph.workflow import create_workflow
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
