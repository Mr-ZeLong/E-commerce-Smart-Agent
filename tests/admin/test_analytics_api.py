import uuid

import pytest

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.complaint import ComplaintTicket
from app.models.observability import GraphExecutionLog
from tests.test_admin_api import create_admin_user, create_regular_user


async def create_graph_execution_log(
    thread_id: str,
    user_id: int,
    intent_category: str = "ORDER",
    final_agent: str = "order_agent",
    confidence_score: float = 0.85,
    needs_human_transfer: bool = False,
    total_latency_ms: int = 1200,
) -> GraphExecutionLog:
    async with async_session_maker() as session:
        log = GraphExecutionLog(
            thread_id=thread_id,
            user_id=user_id,
            intent_category=intent_category,
            final_agent=final_agent,
            confidence_score=confidence_score,
            needs_human_transfer=needs_human_transfer,
            total_latency_ms=total_latency_ms,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def create_complaint_ticket(
    user_id: int, category: str = "product_defect"
) -> ComplaintTicket:
    async with async_session_maker() as session:
        ticket = ComplaintTicket(
            user_id=user_id,
            thread_id=f"thread_{uuid.uuid4().hex[:8]}",
            category=category,
            description="Test complaint",
            expected_resolution="refund",
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket


@pytest.mark.asyncio
async def test_get_csat_trend_analytics(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    from tests.admin.test_feedback_api import create_feedback

    await create_feedback(user.id or 0, f"thread_{uuid.uuid4().hex[:8]}", 0, score=1)

    response = await client.get(
        "/api/v1/admin/analytics/csat?days=30",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "date" in data[0]
    assert "avg_score" in data[0]
    assert "count" in data[0]


@pytest.mark.asyncio
async def test_get_csat_trend_analytics_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/analytics/csat",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_complaint_root_causes(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    await create_complaint_ticket(user.id or 0, category="service")
    await create_complaint_ticket(user.id or 0, category="logistics")

    response = await client.get(
        "/api/v1/admin/analytics/complaint-root-causes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    categories = {item["category"] for item in data}
    assert "service" in categories
    assert "logistics" in categories


@pytest.mark.asyncio
async def test_get_complaint_root_causes_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/analytics/complaint-root-causes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_agent_comparison(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    await create_graph_execution_log(
        thread_id=thread_id,
        user_id=user.id or 0,
        final_agent="order_agent",
        needs_human_transfer=False,
    )
    await create_graph_execution_log(
        thread_id=f"thread_{uuid.uuid4().hex[:8]}",
        user_id=user.id or 0,
        final_agent="order_agent",
        intent_category="COMPLAINT",
        needs_human_transfer=True,
    )

    response = await client.get(
        "/api/v1/admin/analytics/agent-comparison?days=30",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    agents = [item["final_agent"] for item in data]
    assert "order_agent" in agents
    order_item = next(item for item in data if item["final_agent"] == "order_agent")
    assert order_item["total_sessions"] >= 2
    assert order_item["complaint_count"] >= 1
    assert 0.0 <= order_item["transfer_rate"] <= 1.0


@pytest.mark.asyncio
async def test_get_agent_comparison_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/analytics/agent-comparison",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_traces(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    log = await create_graph_execution_log(
        thread_id=thread_id,
        user_id=user.id or 0,
        final_agent="order_agent",
    )

    response = await client.get(
        "/api/v1/admin/analytics/traces?days=30",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "traces" in data
    assert "total" in data
    assert data["total"] >= 1
    trace_ids = [t["id"] for t in data["traces"]]
    assert log.id in trace_ids


@pytest.mark.asyncio
async def test_list_traces_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/analytics/traces",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
