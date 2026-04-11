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
        logistics_agent=AsyncMock(),
        account_agent=AsyncMock(),
        payment_agent=AsyncMock(),
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
        logistics_agent=AsyncMock(),
        account_agent=AsyncMock(),
        payment_agent=AsyncMock(),
        evaluator=mock_eval,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert result.get("answer") == "满100免运费"


@pytest.mark.asyncio
async def test_workflow_logistics_query():
    checkpointer = MemorySaver()

    initial_state = make_agent_state(
        question="我的快递到哪了？",
        thread_id="1__test_logistics",
    )

    mock_router = _mock_agent()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "logistics"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "物流单号: SF1234567890, 状态: 运输中",
        "updated_state": {"order_data": {"tracking_number": "SF1234567890", "status": "运输中"}},
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
        order_agent=AsyncMock(),
        logistics_agent=mock_agent,
        account_agent=AsyncMock(),
        payment_agent=AsyncMock(),
        evaluator=mock_eval,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "物流单号" in result.get("answer", "")


@pytest.mark.asyncio
async def test_workflow_account_query():
    checkpointer = MemorySaver()

    initial_state = make_agent_state(
        question="我的账户余额是多少？",
        thread_id="1__test_account",
    )

    mock_router = _mock_agent()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "account"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "账户余额: ¥128.50",
        "updated_state": {"account_data": {"balance": 128.50}},
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
        order_agent=AsyncMock(),
        logistics_agent=AsyncMock(),
        account_agent=mock_agent,
        payment_agent=AsyncMock(),
        evaluator=mock_eval,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "¥128.50" in result.get("answer", "")


@pytest.mark.asyncio
async def test_workflow_payment_query():
    checkpointer = MemorySaver()

    initial_state = make_agent_state(
        question="我的退款到账了吗？",
        thread_id="1__test_payment",
    )

    mock_router = _mock_agent()
    mock_router.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "payment"},
        "needs_human": False,
        "transfer_reason": None,
    }

    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "退款状态: 已到账",
        "updated_state": {"payment_data": {"refund_status": "已到账"}},
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
        order_agent=AsyncMock(),
        logistics_agent=AsyncMock(),
        account_agent=AsyncMock(),
        payment_agent=mock_agent,
        evaluator=mock_eval,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "已到账" in result.get("answer", "")
