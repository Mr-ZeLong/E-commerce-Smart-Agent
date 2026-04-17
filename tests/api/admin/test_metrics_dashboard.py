"""Tests for the production monitoring dashboard endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.observability import GraphExecutionLog
from app.models.user import User


async def create_admin_user() -> tuple[User, str]:
    unique = uuid.uuid4().hex[:8]
    username = f"admin_{unique}"
    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("adminpass"),
            email=f"{username}@_admin.com",
            full_name="Admin User",
            phone="13800138000",
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id or 0, is_admin=True)
        return user, token


async def create_sample_logs(user: User) -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    async with async_session_maker() as session:
        assert user.id is not None
        logs = [
            GraphExecutionLog(
                thread_id="t1",
                user_id=user.id,
                intent_category="order_query",
                confidence_score=0.85,
                needs_human_transfer=False,
                total_latency_ms=1200,
                context_tokens=150,
                created_at=now - timedelta(hours=2),
            ),
            GraphExecutionLog(
                thread_id="t2",
                user_id=user.id,
                intent_category="refund_apply",
                confidence_score=0.45,
                needs_human_transfer=True,
                total_latency_ms=800,
                context_tokens=200,
                created_at=now - timedelta(hours=1),
            ),
            GraphExecutionLog(
                thread_id="t3",
                user_id=user.id,
                intent_category="order_query",
                confidence_score=0.92,
                needs_human_transfer=False,
                total_latency_ms=1500,
                context_tokens=180,
                created_at=now - timedelta(hours=5),
            ),
        ]
        for log in logs:
            session.add(log)
        await session.commit()


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()
    await create_sample_logs(_admin)

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_sessions_24h"] >= 3
    assert data["total_sessions_7d"] >= 3
    assert 0.0 <= data["transfer_rate_24h"] <= 1.0
    assert 0.0 <= data["containment_rate_24h"] <= 1.0
    assert data["avg_latency_ms_24h"] is not None
    assert data["avg_confidence_24h"] is not None


@pytest.mark.asyncio
async def test_intent_accuracy_trend(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()
    await create_sample_logs(_admin)

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/intent-accuracy?hours=24",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert "hour" in item
        assert "intent_category" in item
        assert "total" in item
        assert "correct" in item
        assert "accuracy" in item


@pytest.mark.asyncio
async def test_transfer_reasons(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()
    await create_sample_logs(_admin)

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/transfer-reasons",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    reasons = [r["reason"] for r in data]
    assert "refund_apply" in reasons


@pytest.mark.asyncio
async def test_token_usage(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()
    await create_sample_logs(_admin)

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/token-usage?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert "date" in item
        assert "input_tokens" in item
        assert "output_tokens" in item
        assert "total_tokens" in item


@pytest.mark.asyncio
async def test_latency_trend(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()
    await create_sample_logs(_admin)

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/latency-trend?hours=24",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert "hour" in item
        assert "avg_latency_ms" in item
        assert "p95_latency_ms" in item
        assert "p99_latency_ms" in item


@pytest.mark.asyncio
async def test_dashboard_alerts(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()
    await create_sample_logs(_admin)

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_rag_precision(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/rag-precision?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_hallucination_rate(client: AsyncClient) -> None:
    _admin, token = await create_admin_user()

    response = await client.get(
        "/api/v1/admin/metrics/dashboard/hallucination-rate?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
