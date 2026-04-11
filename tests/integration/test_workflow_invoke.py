from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.graph import nodes as graph_nodes
from app.graph.workflow import workflow
from app.models.state import make_agent_state


@pytest.mark.asyncio
async def test_workflow_order_query():
    """测试工作流能处理订单查询意图"""
    checkpointer = MemorySaver()
    app_graph = workflow.compile(checkpointer=checkpointer)

    initial_state = make_agent_state(
        question="帮我查下订单 SN20240001",
        thread_id="1__test_order",
    )

    mock_router = AsyncMock()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "order"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = AsyncMock()
    mock_agent.process.return_value = {
        "response": "订单状态：已发货",
        "updated_state": {"order_data": {"order_sn": "SN20240001", "status": "SHIPPED"}},
        "needs_human": False,
        "transfer_reason": None,
    }

    with (
        patch.object(graph_nodes, "router_agent", mock_router),
        patch.object(graph_nodes, "order_agent", mock_agent),
        patch.object(graph_nodes.evaluator, "evaluate", new_callable=AsyncMock) as mock_eval,
    ):
        mock_eval.return_value = {
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
        result = await app_graph.ainvoke(
            cast(Any, initial_state),
            config={"configurable": {"thread_id": initial_state["thread_id"]}},
        )
        assert "answer" in result


@pytest.mark.asyncio
async def test_workflow_policy_query():
    """测试工作流能处理政策咨询意图"""
    checkpointer = MemorySaver()
    app_graph = workflow.compile(checkpointer=checkpointer)

    initial_state = make_agent_state(
        question="运费怎么算？",
        thread_id="1__test_policy",
    )

    mock_router = AsyncMock()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "policy"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = AsyncMock()
    mock_agent.process.return_value = {
        "response": "满100免运费",
        "updated_state": {"retrieval_result": None},
        "needs_human": False,
        "transfer_reason": None,
    }

    with (
        patch.object(graph_nodes, "router_agent", mock_router),
        patch.object(graph_nodes, "policy_agent", mock_agent),
        patch.object(graph_nodes.evaluator, "evaluate", new_callable=AsyncMock) as mock_eval,
    ):
        mock_eval.return_value = {
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
        result = await app_graph.ainvoke(
            cast(Any, initial_state),
            config={"configurable": {"thread_id": initial_state["thread_id"]}},
        )
        assert result.get("answer") == "满100免运费"
