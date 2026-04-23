"""Tests for token usage admin endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.token_usage import TokenUsageLog
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


async def create_sample_token_logs(user: User) -> None:
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        assert user.id is not None
        logs = [
            TokenUsageLog(
                user_id=user.id,
                thread_id="t1",
                agent_type="order_agent",
                input_tokens=500,
                output_tokens=300,
                total_tokens=800,
                query_text="查询订单",
                model_name="qwen-plus",
                created_at=now - timedelta(hours=2),
            ),
            TokenUsageLog(
                user_id=user.id,
                thread_id="t2",
                agent_type="policy_agent",
                input_tokens=1200,
                output_tokens=800,
                total_tokens=2000,
                query_text="退货政策",
                model_name="qwen-plus",
                created_at=now - timedelta(hours=1),
            ),
            TokenUsageLog(
                user_id=user.id,
                thread_id="t3",
                agent_type="order_agent",
                input_tokens=15000,
                output_tokens=5000,
                total_tokens=20000,
                query_text="复杂查询",
                model_name="qwen-plus",
                created_at=now - timedelta(minutes=30),
            ),
        ]
        for log in logs:
            session.add(log)
        await session.commit()


async def create_sample_suggestions(user: User) -> None:
    from app.models.token_usage import OptimizationSuggestion

    now = datetime.now(UTC)
    async with async_session_maker() as session:
        assert user.id is not None
        suggestions = [
            OptimizationSuggestion(
                user_id=user.id,
                thread_id="t3",
                suggestion_type="high_context_window",
                message="Query used 20000 tokens. Consider reducing context.",
                status="pending",
                created_at=now,
            ),
        ]
        for s in suggestions:
            session.add(s)
        await session.commit()


@pytest.mark.asyncio
async def test_token_usage_summary(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_token_logs(admin)

    response = await client.get(
        "/api/v1/admin/token-usage/?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period_days"] == 7
    assert data["total_tokens"] == 22800
    assert data["query_count"] == 3
    assert data["unique_users"] == 1


@pytest.mark.asyncio
async def test_token_usage_by_user(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_token_logs(admin)

    response = await client.get(
        f"/api/v1/admin/token-usage/by-user/?user_id={admin.id}&days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2  # daily + period aggregates


@pytest.mark.asyncio
async def test_token_usage_by_agent(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_token_logs(admin)

    response = await client.get(
        "/api/v1/admin/token-usage/by-agent/?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2  # order_agent + policy_agent
    agent_types = {item["agent_type"] for item in data}
    assert "order_agent" in agent_types
    assert "policy_agent" in agent_types


@pytest.mark.asyncio
async def test_high_cost_queries(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_token_logs(admin)

    response = await client.get(
        "/api/v1/admin/token-usage/high-cost/?threshold=10000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # All returned queries should have total_tokens >= threshold
    for item in data:
        assert item["total_tokens"] >= 10000


@pytest.mark.asyncio
async def test_token_anomalies(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_token_logs(admin)

    response = await client.get(
        "/api/v1/admin/token-usage/anomalies/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should detect high single query
    high_queries = [a for a in data if a["type"] == "single_query_high"]
    assert len(high_queries) >= 1


@pytest.mark.asyncio
async def test_optimization_suggestions(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_token_logs(admin)
    await create_sample_suggestions(admin)

    response = await client.get(
        "/api/v1/admin/token-usage/suggestions/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should have suggestion for high context window (20000 tokens query)
    high_ctx = [s for s in data if s["suggestion_type"] == "high_context_window"]
    assert len(high_ctx) >= 1
