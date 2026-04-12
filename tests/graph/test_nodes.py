from unittest.mock import AsyncMock

import pytest
from langgraph.types import Command

from app.graph.nodes import (
    build_evaluator_node,
    build_order_node,
    build_policy_node,
    build_router_node,
    decider_node,
)
from app.models.state import make_agent_state


def _mock_agent():
    return AsyncMock()


@pytest.mark.asyncio
async def test_router_node_direct_response():
    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "您好！",
        "updated_state": {"next_agent": "supervisor", "iteration_count": 1},
    }

    node = build_router_node(mock_agent)
    state = make_agent_state(
        question="你好",
        thread_id="t1",
        iteration_count=0,
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update is not None
    assert result.update["answer"] == "您好！"
    assert result.update["iteration_count"] == 1


@pytest.mark.asyncio
async def test_router_node_routes_to_supervisor():
    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "",
        "updated_state": {"next_agent": "policy_agent", "iteration_count": 1},
    }

    node = build_router_node(mock_agent)
    state = make_agent_state(
        question="运费怎么算",
        thread_id="t2",
        iteration_count=0,
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "memory_node"
    assert result.update is not None
    assert result.update["next_agent"] == "policy_agent"
    assert result.update["iteration_count"] == 1


@pytest.mark.asyncio
async def test_router_node_missing_next_agent():
    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "",
        "updated_state": {"needs_human_transfer": True},
    }

    node = build_router_node(mock_agent)
    state = make_agent_state(
        question="xxx",
        thread_id="t5",
        iteration_count=0,
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "memory_node"
    assert result.update is not None
    assert result.update["needs_human_transfer"] is True


@pytest.mark.asyncio
async def test_policy_node():
    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "运费满100免运费",
        "updated_state": {"context": ["policy chunk"]},
    }

    node = build_policy_node(mock_agent)
    state = make_agent_state(question="运费", thread_id="t6")
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "evaluator_node"
    assert result.update is not None
    assert result.update["answer"] == "运费满100免运费"
    assert result.update["context"] == ["policy chunk"]


@pytest.mark.asyncio
async def test_order_node():
    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "您的订单已发货",
        "updated_state": {"order_data": {"status": "shipped"}},
    }

    node = build_order_node(mock_agent)
    state = make_agent_state(question="订单", thread_id="t7")
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "evaluator_node"
    assert result.update is not None
    assert result.update["answer"] == "您的订单已发货"
    assert result.update["order_data"]["status"] == "shipped"


@pytest.mark.asyncio
async def test_policy_node_returns_updates():
    mock_agent = _mock_agent()
    mock_agent.process.return_value = {
        "response": "请转人工",
        "updated_state": {
            "needs_human_transfer": True,
            "transfer_reason": "policy_specialist_request",
        },
    }

    node = build_policy_node(mock_agent)
    state = make_agent_state(question="投诉", thread_id="t8")
    result = await node(state)

    assert result.update is not None
    assert result.update["needs_human_transfer"] is True
    assert result.update["transfer_reason"] == "policy_specialist_request"


@pytest.mark.asyncio
async def test_evaluator_node_skips_when_needs_human():
    node = build_evaluator_node(_mock_agent())
    state = make_agent_state(
        question="转人工",
        answer="请转人工",
        iteration_count=1,
        needs_human_transfer=True,
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update == {}


@pytest.mark.asyncio
async def test_evaluator_node_low_confidence_retries():
    eval_result = {
        "confidence_score": 0.2,
        "confidence_signals": {"rag": {"score": 0.2, "reason": "缺失"}},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "auto",
    }
    mock_eval = _mock_agent()
    mock_eval.evaluate.return_value = eval_result

    node = build_evaluator_node(mock_eval)
    state = make_agent_state(
        answer="不确定",
        question="怎么退货",
        iteration_count=1,
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "router_node"
    assert result.update is not None
    assert result.update["confidence_score"] == 0.2
    assert "needs_human_transfer" not in result.update
    assert "audit_level" not in result.update
    assert "transfer_reason" not in result.update


@pytest.mark.asyncio
async def test_evaluator_node_retry_excludes_transfer_flags():
    """即使 evaluator 返回 needs_human_transfer=True，retry 更新中也不应包含该标志"""
    eval_result = {
        "confidence_score": 0.1,
        "confidence_signals": {"rag": {"score": 0.1, "reason": "缺失"}},
        "needs_human_transfer": True,
        "transfer_reason": "置信度不足",
        "audit_level": "manual",
    }
    mock_eval = _mock_agent()
    mock_eval.evaluate.return_value = eval_result

    node = build_evaluator_node(mock_eval)
    state = make_agent_state(
        answer="不确定",
        question="怎么退货",
        iteration_count=1,
    )
    result = await node(state)

    assert result.goto == "router_node"
    assert result.update is not None
    assert result.update["confidence_score"] == 0.1
    assert "needs_human_transfer" not in result.update
    assert "audit_level" not in result.update
    assert "transfer_reason" not in result.update


@pytest.mark.asyncio
async def test_evaluator_node_high_confidence_goes_to_decider():
    eval_result = {
        "confidence_score": 0.85,
        "confidence_signals": {"rag": {"score": 0.9, "reason": "匹配"}},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "none",
    }
    mock_eval = _mock_agent()
    mock_eval.evaluate.return_value = eval_result

    node = build_evaluator_node(mock_eval)
    state = make_agent_state(
        answer="运费满100免运费",
        question="运费怎么算",
        iteration_count=1,
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update is not None
    assert result.update["confidence_score"] == 0.85


@pytest.mark.asyncio
async def test_evaluator_node_boundary_confidence_retries():
    eval_result = {
        "confidence_score": 0.3,
        "confidence_signals": {},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "auto",
    }
    mock_eval = _mock_agent()
    mock_eval.evaluate.return_value = eval_result

    node = build_evaluator_node(mock_eval)
    state = make_agent_state(
        answer="一般",
        question="问题",
        iteration_count=1,
    )
    result = await node(state)

    assert result.goto == "decider_node"


def test_decider_node_normal():
    state = make_agent_state(
        question="运费",
        answer="运费满100免运费",
        audit_level="none",
        confidence_score=0.85,
        confidence_signals={"rag": {"score": 0.9}},
        needs_human_transfer=False,
        transfer_reason=None,
    )
    result = decider_node(state)

    assert result["answer"] == "运费满100免运费"
    assert result["needs_human_transfer"] is False
    assert result["audit_level"] == "none"
    assert result["confidence_score"] == 0.85
    assert result["answer"] == "运费满100免运费"


def test_decider_node_transfer():
    state = make_agent_state(
        question="投诉",
        answer="请转人工",
        audit_level="manual",
        confidence_score=0.0,
        confidence_signals={},
        needs_human_transfer=True,
        transfer_reason="specialist_requested_transfer",
    )
    result = decider_node(state)

    assert result["needs_human_transfer"] is True
    assert result["transfer_reason"] == "specialist_requested_transfer"
    assert result["audit_level"] == "manual"


def test_decider_node_direct_response_from_router():
    """router 直接回答（问候/澄清）confidence_score 为 None 时不应误判为 missing_evaluation"""
    state = make_agent_state(
        question="你好",
        answer="您好！有什么可以帮您？",
        needs_human_transfer=False,
    )
    result = decider_node(state)

    assert result["needs_human_transfer"] is False
    assert result["transfer_reason"] is None
    assert result["audit_level"] == "auto"
    assert result["confidence_score"] == 1.0
    assert result["answer"] == "您好！有什么可以帮您？"
