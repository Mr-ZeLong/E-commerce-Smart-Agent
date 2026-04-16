import uuid

import pytest

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.audit import AuditAction, AuditLog, AuditTriggerType, RiskLevel
from app.models.observability import GraphExecutionLog, GraphNodeLog
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User
from tests.test_admin_api import create_admin_user, create_regular_user


async def create_graph_execution_log(
    thread_id: str,
    user_id: int,
    final_agent: str = "order_agent",
    confidence_score: float = 0.85,
    needs_human_transfer: bool = False,
    total_latency_ms: int = 1200,
) -> GraphExecutionLog:
    async with async_session_maker() as session:
        log = GraphExecutionLog(
            thread_id=thread_id,
            user_id=user_id,
            final_agent=final_agent,
            confidence_score=confidence_score,
            needs_human_transfer=needs_human_transfer,
            total_latency_ms=total_latency_ms,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def create_graph_node_log(
    execution_id: int,
    node_name: str,
    latency_ms: int = 100,
) -> GraphNodeLog:
    async with async_session_maker() as session:
        log = GraphNodeLog(
            execution_id=execution_id,
            node_name=node_name,
            latency_ms=latency_ms,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def create_audit_log_for_confidence(user: User) -> AuditLog:
    async with async_session_maker() as session:
        from app.core.utils import build_thread_id

        log = AuditLog(
            thread_id=build_thread_id(user.id or 0, f"test_thread_{uuid.uuid4().hex[:8]}"),
            user_id=user.id or 0,
            trigger_reason="Low confidence",
            risk_level=RiskLevel.LOW,
            action=AuditAction.PENDING,
            trigger_type=AuditTriggerType.CONFIDENCE,
            context_snapshot={},
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def create_order_and_refund(user: User) -> tuple[Order, RefundApplication]:
    from decimal import Decimal

    async with async_session_maker() as session:
        order = Order(
            order_sn=f"ORD{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id or 0,
            status=OrderStatus.DELIVERED,
            total_amount=Decimal("199.99"),
            items=[{"name": "Test Item", "price": 199.99}],
            shipping_address="Test Address",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        assert order.id is not None

        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id or 0,
            status=RefundStatus.PENDING,
            reason_detail="Test refund",
            refund_amount=Decimal("199.99"),
        )
        session.add(refund)
        await session.commit()
        await session.refresh(refund)
        return order, refund


@pytest.mark.asyncio
async def test_get_confidence_tasks(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    audit_log = await create_audit_log_for_confidence(user)

    response = await client.get(
        "/api/v1/admin/confidence-tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    audit_ids = [task["audit_log_id"] for task in data]
    assert audit_log.id in audit_ids


@pytest.mark.asyncio
async def test_get_confidence_tasks_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/confidence-tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_session_metrics(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    assert user.id is not None
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    await create_graph_execution_log(thread_id=thread_id, user_id=user.id)

    response = await client.get(
        "/api/v1/admin/metrics/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "24h" in data
    assert "7d" in data
    assert "30d" in data
    assert data["24h"] >= 1


@pytest.mark.asyncio
async def test_get_session_metrics_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/metrics/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_transfer_metrics(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    await create_graph_execution_log(
        thread_id=f"thread_{uuid.uuid4().hex[:8]}",
        user_id=user.id or 0,
        final_agent="order_agent",
        needs_human_transfer=True,
    )
    await create_graph_execution_log(
        thread_id=f"thread_{uuid.uuid4().hex[:8]}",
        user_id=user.id or 0,
        final_agent="order_agent",
        needs_human_transfer=False,
    )

    response = await client.get(
        "/api/v1/admin/metrics/transfers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    agents = [m["final_agent"] for m in data]
    assert "order_agent" in agents
    order_metric = next(m for m in data if m["final_agent"] == "order_agent")
    assert order_metric["total"] >= 2
    assert order_metric["transfers"] >= 1
    assert "transfer_rate" in order_metric


@pytest.mark.asyncio
async def test_get_transfer_metrics_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/metrics/transfers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_confidence_metrics(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    await create_graph_execution_log(
        thread_id=f"thread_{uuid.uuid4().hex[:8]}",
        user_id=user.id or 0,
        final_agent="policy_agent",
        confidence_score=0.92,
    )

    response = await client.get(
        "/api/v1/admin/metrics/confidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    agents = [m["final_agent"] for m in data]
    assert "policy_agent" in agents
    policy_metric = next(m for m in data if m["final_agent"] == "policy_agent")
    assert policy_metric["avg_confidence"] is not None


@pytest.mark.asyncio
async def test_get_confidence_metrics_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/metrics/confidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_latency_metrics(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    exec_log = await create_graph_execution_log(
        thread_id=f"thread_{uuid.uuid4().hex[:8]}", user_id=user.id or 0
    )
    assert exec_log.id is not None
    await create_graph_node_log(execution_id=exec_log.id, node_name="router_node", latency_ms=150)
    await create_graph_node_log(execution_id=exec_log.id, node_name="router_node", latency_ms=250)

    response = await client.get(
        "/api/v1/admin/metrics/latency",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    nodes = [m["node_name"] for m in data]
    assert "router_node" in nodes
    router_metric = next(m for m in data if m["node_name"] == "router_node")
    assert router_metric["p99_latency_ms"] is not None


@pytest.mark.asyncio
async def test_get_latency_metrics_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/metrics/latency",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_evaluation_dataset(client):
    _admin, token = await create_admin_user()

    response = await client.get(
        "/api/v1/admin/evaluation/dataset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "records" in data


@pytest.mark.asyncio
async def test_get_evaluation_dataset_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/evaluation/dataset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_run_evaluation(client, deterministic_llm, redis_client):
    from langgraph.graph import END, START, StateGraph

    from app.intent.service import IntentRecognitionService
    from app.main import app
    from app.models.state import AgentState

    def _build_graph():
        def _node(state: AgentState):
            return {
                "answer": "预期答案",
                "retrieval_result": {"chunks": ["政策A", "政策B"]},
            }

        workflow = StateGraph(AgentState)  # type: ignore
        workflow.add_node("policy_agent", _node)
        workflow.add_edge(START, "policy_agent")
        workflow.add_edge("policy_agent", END)
        return workflow.compile()

    intent_service = IntentRecognitionService(llm=deterministic_llm, redis_client=redis_client)
    deterministic_llm.responses = [("correctness", "1.0")]

    original_intent_service = getattr(app.state, "intent_service", None)
    original_llm = getattr(app.state, "llm", None)
    original_app_graph = getattr(app.state, "app_graph", None)

    app.state.intent_service = intent_service
    app.state.llm = deterministic_llm
    app.state.app_graph = _build_graph()

    _admin, token = await create_admin_user()

    try:
        response = await client.post(
            "/api/v1/admin/evaluation/run",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.state.intent_service = original_intent_service
        app.state.llm = original_llm
        app.state.app_graph = original_app_graph

    assert response.status_code == 200
    data = response.json()
    assert "intent_accuracy" in data
    assert "slot_recall" in data
    assert "rag_precision" in data
    assert "answer_correctness" in data
    assert "total_records" in data


@pytest.mark.asyncio
async def test_run_evaluation_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.post(
        "/api/v1/admin/evaluation/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
