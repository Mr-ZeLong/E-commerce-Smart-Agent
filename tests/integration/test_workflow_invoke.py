from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.graph.workflow import create_workflow
from app.models.state import make_agent_state


def _mock_agent():
    return AsyncMock()


@pytest.mark.asyncio
async def test_workflow_order_query():
    checkpointer = MemorySaver()

    initial_state = make_agent_state(
        question="帮我查下订单 SN20240001",
        thread_id="1__test_order",
    )

    mock_router = _mock_agent()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "order_agent"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "订单状态：已发货",
        "updated_state": {"order_data": {"order_sn": "SN20240001", "status": "SHIPPED"}},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_eval = _mock_agent()
    mock_eval.evaluate.return_value = {
        "confidence_score": 0.9,
        "confidence_signals": {},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "none",
    }

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=AsyncMock(),
        order_agent=mock_agent,
        evaluator=mock_eval,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "answer" in result


@pytest.mark.asyncio
async def test_workflow_policy_query():
    checkpointer = MemorySaver()

    initial_state = make_agent_state(
        question="运费怎么算？",
        thread_id="1__test_policy",
    )

    mock_router = _mock_agent()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "policy_agent"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "满100免运费",
        "updated_state": {"retrieval_result": None},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_eval = _mock_agent()
    mock_eval.evaluate.return_value = {
        "confidence_score": 0.9,
        "confidence_signals": {},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "none",
    }

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=mock_agent,
        order_agent=AsyncMock(),
        evaluator=mock_eval,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert result.get("answer") == "满100免运费"
