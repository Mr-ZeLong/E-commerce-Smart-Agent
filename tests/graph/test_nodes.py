from unittest.mock import AsyncMock, patch

import pytest
from langgraph.types import Command

from app.agents.base import AgentResult
from app.graph import nodes as graph_nodes
from app.models.state import make_agent_state


@pytest.fixture(autouse=True)
def reset_graph_singletons():
    """每个测试前重置全局单例，避免状态泄漏"""
    graph_nodes._router_agent = None
    graph_nodes._policy_agent = None
    graph_nodes._order_agent = None
    yield
    graph_nodes._router_agent = None
    graph_nodes._policy_agent = None
    graph_nodes._order_agent = None


@pytest.mark.asyncio
async def test_router_node_direct_response():
    """router_node 在直接回复场景下返回 decider_node"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="您好！",
        updated_state={"intent": "OTHER", "next_agent": "supervisor"},
    )
    graph_nodes._router_agent = mock_agent

    state = make_agent_state(
        question="你好",
        thread_id="t1",
        iteration_count=0,
    )
    result = await graph_nodes.router_node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update["answer"] == "您好！"
    assert result.update["iteration_count"] == 1


@pytest.mark.asyncio
async def test_router_node_routes_to_policy():
    """router_node 将 policy 意图路由到 policy_agent"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="",
        updated_state={"intent": "POLICY", "next_agent": "policy"},
    )
    graph_nodes._router_agent = mock_agent

    state = make_agent_state(
        question="运费怎么算",
        thread_id="t2",
        iteration_count=0,
    )
    result = await graph_nodes.router_node(state)

    assert isinstance(result, Command)
    assert result.goto == "policy_agent"
    assert result.update["next_agent"] == "policy"
    assert result.update["iteration_count"] == 1


@pytest.mark.asyncio
async def test_router_node_routes_to_order():
    """router_node 将 order 意图路由到 order_agent"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="",
        updated_state={"intent": "ORDER", "next_agent": "order"},
    )
    graph_nodes._router_agent = mock_agent

    state = make_agent_state(
        question="我的订单到哪了",
        thread_id="t3",
        iteration_count=0,
    )
    result = await graph_nodes.router_node(state)

    assert isinstance(result, Command)
    assert result.goto == "order_agent"
    assert result.update["next_agent"] == "order"


@pytest.mark.asyncio
async def test_router_node_iteration_exceeded():
    """router_node 在迭代次数超过 5 时返回转人工"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="",
        updated_state={"intent": "ORDER", "next_agent": "order"},
    )
    graph_nodes._router_agent = mock_agent

    state = make_agent_state(
        question="我的订单",
        thread_id="t4",
        iteration_count=6,
    )
    result = await graph_nodes.router_node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert "系统处理步数过多" in result.update["answer"]
    assert result.update["needs_human_transfer"] is True


@pytest.mark.asyncio
async def test_router_node_missing_next_agent():
    """router_node 在未识别到 next_agent 时返回转人工"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="",
        updated_state={"intent": "OTHER"},
    )
    graph_nodes._router_agent = mock_agent

    state = make_agent_state(
        question="xxx",
        thread_id="t5",
        iteration_count=0,
    )
    result = await graph_nodes.router_node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update["needs_human_transfer"] is True


@pytest.mark.asyncio
async def test_policy_node():
    """policy_node 调用 PolicyAgent 并路由到 evaluator_node"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="运费满100免运费",
        updated_state={"context": ["policy chunk"]},
    )
    graph_nodes._policy_agent = mock_agent

    state = make_agent_state(question="运费", thread_id="t6")
    result = await graph_nodes.policy_node(state)

    assert isinstance(result, Command)
    assert result.goto == "evaluator_node"
    assert result.update["answer"] == "运费满100免运费"
    assert result.update["context"] == ["policy chunk"]


@pytest.mark.asyncio
async def test_order_node():
    """order_node 调用 OrderAgent 并路由到 evaluator_node"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="您的订单已发货",
        updated_state={"order_data": {"status": "shipped"}},
    )
    graph_nodes._order_agent = mock_agent

    state = make_agent_state(question="订单", thread_id="t7")
    result = await graph_nodes.order_node(state)

    assert isinstance(result, Command)
    assert result.goto == "evaluator_node"
    assert result.update["answer"] == "您的订单已发货"
    assert result.update["order_data"]["status"] == "shipped"


@pytest.mark.asyncio
async def test_policy_node_needs_human():
    """policy_node 在 AgentResult 标记 needs_human 时传递转人工字段"""
    mock_agent = AsyncMock()
    mock_agent.process.return_value = AgentResult(
        response="请转人工",
        updated_state={},
        needs_human=True,
        transfer_reason="policy_specialist_request",
    )
    graph_nodes._policy_agent = mock_agent

    state = make_agent_state(question="投诉", thread_id="t8")
    result = await graph_nodes.policy_node(state)

    assert result.update["needs_human_transfer"] is True
    assert result.update["transfer_reason"] == "policy_specialist_request"


@pytest.mark.asyncio
async def test_evaluator_node_skips_when_needs_human():
    """evaluator_node 在 needs_human_transfer 为 True 时直接跳过"""
    state = make_agent_state(
        question="转人工",
        answer="请转人工",
        iteration_count=1,
    )
    state["needs_human_transfer"] = True
    result = await graph_nodes.evaluator_node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update == {}


@pytest.mark.asyncio
async def test_evaluator_node_low_confidence_retries():
    """evaluator_node 在置信度极低且未超限时返回 router_node"""
    eval_result = {
        "confidence_score": 0.2,
        "confidence_signals": {"rag": {"score": 0.2, "reason": "缺失"}},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "auto",
    }
    with patch.object(
        graph_nodes.ConfidenceEvaluator, "evaluate", new_callable=AsyncMock
    ) as mock_eval:
        mock_eval.return_value = eval_result
        state = make_agent_state(
            answer="不确定",
            question="怎么退货",
            iteration_count=1,
        )
        result = await graph_nodes.evaluator_node(state)

    assert isinstance(result, Command)
    assert result.goto == "router_node"
    assert result.update["confidence_score"] == 0.2


@pytest.mark.asyncio
async def test_evaluator_node_high_confidence_goes_to_decider():
    """evaluator_node 在置信度正常时返回 decider_node"""
    eval_result = {
        "confidence_score": 0.85,
        "confidence_signals": {"rag": {"score": 0.9, "reason": "匹配"}},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "none",
    }
    with patch.object(
        graph_nodes.ConfidenceEvaluator, "evaluate", new_callable=AsyncMock
    ) as mock_eval:
        mock_eval.return_value = eval_result
        state = make_agent_state(
            answer="运费满100免运费",
            question="运费怎么算",
            iteration_count=1,
        )
        result = await graph_nodes.evaluator_node(state)

    assert isinstance(result, Command)
    assert result.goto == "decider_node"
    assert result.update["confidence_score"] == 0.85


@pytest.mark.asyncio
async def test_evaluator_node_boundary_confidence_retries():
    """evaluator_node 在 confidence_score==0.3 时不重试，直接到 decider_node"""
    eval_result = {
        "confidence_score": 0.3,
        "confidence_signals": {},
        "needs_human_transfer": False,
        "transfer_reason": None,
        "audit_level": "auto",
    }
    with patch.object(
        graph_nodes.ConfidenceEvaluator, "evaluate", new_callable=AsyncMock
    ) as mock_eval:
        mock_eval.return_value = eval_result
        state = make_agent_state(
            answer="一般",
            question="问题",
            iteration_count=1,
        )
        result = await graph_nodes.evaluator_node(state)

    assert result.goto == "decider_node"


def test_decider_node_normal():
    """decider_node 正常返回决策结果"""
    state = make_agent_state(
        question="运费",
        answer="运费满100免运费",
        audit_level="none",
        confidence_score=0.85,
        confidence_signals={"rag": {"score": 0.9}},
        intent="POLICY",
    )
    state["needs_human_transfer"] = False
    state["transfer_reason"] = None
    result = graph_nodes.decider_node(state)

    assert result["answer"] == "运费满100免运费"
    assert result["needs_human_transfer"] is False
    assert result["audit_level"] == "none"
    assert result["confidence_score"] == 0.85
    assert result["intent"] == "POLICY"


def test_decider_node_transfer():
    """decider_node 在需要转人工时返回正确字段"""
    state = make_agent_state(
        question="投诉",
        answer="请转人工",
        audit_level="manual",
        confidence_score=0.0,
        confidence_signals={},
        intent="ORDER",
    )
    state["needs_human_transfer"] = True
    state["transfer_reason"] = "specialist_requested_transfer"
    result = graph_nodes.decider_node(state)

    assert result["needs_human_transfer"] is True
    assert result["transfer_reason"] == "specialist_requested_transfer"
    assert result["audit_level"] == "manual"
