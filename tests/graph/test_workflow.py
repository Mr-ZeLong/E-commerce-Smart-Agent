from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.graph.workflow import create_workflow


@pytest.mark.asyncio
async def test_workflow_compiles():
    checkpointer = MemorySaver()
    app_graph = create_workflow(
        router_agent=AsyncMock(),
        policy_agent=AsyncMock(),
        order_agent=AsyncMock(),
        logistics_agent=AsyncMock(),
        account_agent=AsyncMock(),
        payment_agent=AsyncMock(),
        evaluator=AsyncMock(),
    ).compile(checkpointer=checkpointer)
    assert app_graph is not None
