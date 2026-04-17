from typing import Any, cast

import pytest

from app.graph.workflow import create_workflow
from app.models.state import make_agent_state
from tests._agents import DeterministicAgent, DeterministicEvaluator, DeterministicSupervisor


def _supervisor_mock(next_agent: str):
    return DeterministicSupervisor(
        process_result={
            "response": "",
            "updated_state": {
                "next_agent": next_agent,
                "execution_mode": "serial",
                "pending_agent_results": [next_agent],
            },
        }
    )


@pytest.mark.asyncio
async def test_workflow_order_query(deterministic_llm, redis_checkpointer):
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="帮我查下订单 SN20240001",
        thread_id="1__test_order",
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "order_agent"},
            "needs_human": False,
            "transfer_reason": None,
        }
    )

    mock_agent = DeterministicAgent(
        name="order_agent",
        process_result={
            "response": "订单状态：已发货",
            "updated_state": {"order_data": {"order_sn": "SN20240001", "status": "SHIPPED"}},
            "needs_human": False,
            "transfer_reason": None,
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=DeterministicAgent(),
        order_agent=mock_agent,
        logistics_agent=DeterministicAgent(),
        account_agent=DeterministicAgent(),
        payment_agent=DeterministicAgent(),
        evaluator=mock_eval,
        supervisor_agent=_supervisor_mock("order_agent"),
        llm=deterministic_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "answer" in result


@pytest.mark.asyncio
async def test_workflow_policy_query(deterministic_llm, redis_checkpointer):
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="运费怎么算？",
        thread_id="1__test_policy",
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "policy_agent"},
            "needs_human": False,
            "transfer_reason": None,
        }
    )

    mock_agent = DeterministicAgent(
        name="policy_agent",
        process_result={
            "response": "满100免运费",
            "updated_state": {"retrieval_result": None},
            "needs_human": False,
            "transfer_reason": None,
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=mock_agent,
        order_agent=DeterministicAgent(),
        logistics_agent=DeterministicAgent(),
        account_agent=DeterministicAgent(),
        payment_agent=DeterministicAgent(),
        evaluator=mock_eval,
        supervisor_agent=_supervisor_mock("policy_agent"),
        llm=deterministic_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert result.get("answer") == "满100免运费"


@pytest.mark.asyncio
async def test_workflow_logistics_query(deterministic_llm, redis_checkpointer):
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="我的快递到哪了？",
        thread_id="1__test_logistics",
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "logistics"},
            "needs_human": False,
            "transfer_reason": None,
        }
    )

    mock_agent = DeterministicAgent(
        name="logistics",
        process_result={
            "response": "物流单号: SF1234567890, 状态: 运输中",
            "updated_state": {
                "order_data": {"tracking_number": "SF1234567890", "status": "运输中"}
            },
            "needs_human": False,
            "transfer_reason": None,
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=DeterministicAgent(),
        order_agent=DeterministicAgent(),
        logistics_agent=mock_agent,
        account_agent=DeterministicAgent(),
        payment_agent=DeterministicAgent(),
        evaluator=mock_eval,
        supervisor_agent=_supervisor_mock("logistics"),
        llm=deterministic_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "物流单号" in result.get("answer", "")


@pytest.mark.asyncio
async def test_workflow_account_query(deterministic_llm, redis_checkpointer):
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="我的账户余额是多少？",
        thread_id="1__test_account",
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "account"},
            "needs_human": False,
            "transfer_reason": None,
        }
    )

    mock_agent = DeterministicAgent(
        name="account",
        process_result={
            "response": "账户余额: ¥128.50",
            "updated_state": {"account_data": {"balance": 128.50}},
            "needs_human": False,
            "transfer_reason": None,
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=DeterministicAgent(),
        order_agent=DeterministicAgent(),
        logistics_agent=DeterministicAgent(),
        account_agent=mock_agent,
        payment_agent=DeterministicAgent(),
        evaluator=mock_eval,
        supervisor_agent=_supervisor_mock("account"),
        llm=deterministic_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "¥128.50" in result.get("answer", "")


@pytest.mark.asyncio
async def test_workflow_payment_query(deterministic_llm, redis_checkpointer):
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="我的退款到账了吗？",
        thread_id="1__test_payment",
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "payment"},
            "needs_human": False,
            "transfer_reason": None,
        }
    )

    mock_agent = DeterministicAgent(
        name="payment",
        process_result={
            "response": "退款状态: 已到账",
            "updated_state": {"payment_data": {"refund_status": "已到账"}},
            "needs_human": False,
            "transfer_reason": None,
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=DeterministicAgent(),
        order_agent=DeterministicAgent(),
        logistics_agent=DeterministicAgent(),
        account_agent=DeterministicAgent(),
        payment_agent=mock_agent,
        evaluator=mock_eval,
        supervisor_agent=_supervisor_mock("payment"),
        llm=deterministic_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )
    assert "已到账" in result.get("answer", "")


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_workflow_real_llm_synthesis(real_llm, redis_checkpointer):
    """Integration test with real LLM for the synthesis node.

    Uses deterministic agents for routing and expert agents, but exercises
    the synthesis node with a real LLM to verify end-to-end response generation.
    """
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="查订单顺便问下退货政策",
        thread_id="1__test_real_llm",
        intent_result={"primary_intent": "ORDER"},
        slots={"pending_intents": [{"primary_intent": "POLICY"}]},
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "order_agent"},
        }
    )

    mock_order = DeterministicAgent(
        name="order_agent",
        process_result={
            "response": "订单已发货",
            "updated_state": {"order_data": {"status": "SHIPPED"}},
        },
    )

    mock_policy = DeterministicAgent(
        name="policy_agent",
        process_result={
            "response": "7天无理由退货",
            "updated_state": {"retrieval_result": None},
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    supervisor = DeterministicSupervisor(
        process_result={
            "response": "",
            "updated_state": {
                "next_agent": "order_agent",
                "execution_mode": "parallel",
                "pending_agent_results": ["order_agent", "policy_agent"],
            },
        }
    )

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=mock_policy,
        order_agent=mock_order,
        logistics_agent=DeterministicAgent(),
        account_agent=DeterministicAgent(),
        payment_agent=DeterministicAgent(),
        evaluator=mock_eval,
        supervisor_agent=supervisor,
        llm=real_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )

    assert result.get("answer")
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0


@pytest.mark.asyncio
async def test_workflow_parallel_multi_intent(deterministic_llm, redis_checkpointer):
    checkpointer = redis_checkpointer

    initial_state = make_agent_state(
        question="查订单顺便问下退货政策",
        thread_id="1__test_parallel",
        intent_result={"primary_intent": "ORDER"},
        slots={"pending_intents": [{"primary_intent": "POLICY"}]},
    )

    mock_router = DeterministicAgent(
        process_result={
            "response": "",
            "updated_state": {"next_agent": "order_agent"},
        }
    )

    mock_order = DeterministicAgent(
        name="order_agent",
        process_result={
            "response": "订单已发货",
            "updated_state": {"order_data": {"status": "SHIPPED"}},
        },
    )

    mock_policy = DeterministicAgent(
        name="policy_agent",
        process_result={
            "response": "7天无理由退货",
            "updated_state": {"retrieval_result": None},
        },
    )

    mock_eval = DeterministicEvaluator(
        evaluate_result={
            "confidence_score": 0.9,
            "confidence_signals": {},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "none",
        }
    )

    supervisor = DeterministicSupervisor(
        process_result={
            "response": "",
            "updated_state": {
                "next_agent": "order_agent",
                "execution_mode": "parallel",
                "pending_agent_results": ["order_agent", "policy_agent"],
            },
        }
    )

    deterministic_llm.responses = [("整合员", "订单已发货，支持7天无理由退货")]

    workflow = create_workflow(
        router_agent=mock_router,
        policy_agent=mock_policy,
        order_agent=mock_order,
        logistics_agent=DeterministicAgent(),
        account_agent=DeterministicAgent(),
        payment_agent=DeterministicAgent(),
        evaluator=mock_eval,
        supervisor_agent=supervisor,
        llm=deterministic_llm,
    )
    app_graph = workflow.compile(checkpointer=checkpointer)
    result = await app_graph.ainvoke(
        cast(Any, initial_state),
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    )

    sub_answers = result.get("sub_answers", [])
    agents = {sa["agent"] for sa in sub_answers}
    assert "order_agent" in agents
    assert "policy_agent" in agents
    assert result.get("answer")
