import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.memory import AgentConfig, RoutingRule
from tests.test_admin_api import create_admin_user


async def create_agent_config(agent_name: str) -> AgentConfig:
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="original prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)
        return config


async def create_routing_rule(intent_category: str, target_agent: str) -> RoutingRule:
    async with async_session_maker() as session:
        rule = RoutingRule(
            intent_category=intent_category,
            target_agent=target_agent,
            priority=1,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


@pytest.mark.asyncio
async def test_list_agent_configs(client):
    _admin, token = await create_admin_user()
    await create_agent_config("policy_agent")
    await create_routing_rule("POLICY", "policy_agent")

    response = await client.get(
        "/api/v1/_admin/agents/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "configs" in data
    assert "routing_rules" in data
    agent_names = [c["agent_name"] for c in data["configs"]]
    assert "policy_agent" in agent_names
    intent_categories = [r["intent_category"] for r in data["routing_rules"]]
    assert "POLICY" in intent_categories


@pytest.mark.asyncio
async def test_list_agent_configs_rejects_non_admin(client):
    from app.models.user import User

    async with async_session_maker() as session:
        user = User(
            username=f"user_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("pass"),
            email=f"user_{uuid.uuid4().hex[:8]}@test.com",
            full_name="Regular User",
            phone="13900139000",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/_admin/agents/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_agent_config(client):
    _admin, token = await create_admin_user()
    await create_agent_config("order_agent")

    with patch("app.api.v1._admin.agent_config.create_redis_client") as mock_redis_factory:
        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        response = await client.post(
            "/api/v1/_admin/agents/config/order_agent",
            headers={"Authorization": f"Bearer {token}"},
            json={"system_prompt": "updated prompt", "confidence_threshold": 0.8},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated" in data["message"].lower() or "success" in data["message"].lower()

    async with async_session_maker() as session:
        result = await session.exec(
            select(AgentConfig).where(AgentConfig.agent_name == "order_agent")
        )
        updated = result.one()
        assert updated.system_prompt == "updated prompt"
        assert updated.previous_system_prompt == "original prompt"
        assert updated.confidence_threshold == 0.8

    mock_redis.delete.assert_awaited_once_with("agent_config:order_agent")


@pytest.mark.asyncio
async def test_update_agent_config_not_found(client):
    _admin, token = await create_admin_user()

    with patch("app.api.v1._admin.agent_config.create_redis_client") as mock_redis_factory:
        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        response = await client.post(
            "/api/v1/_admin/agents/config/nonexistent_agent",
            headers={"Authorization": f"Bearer {token}"},
            json={"system_prompt": "prompt"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rollback_agent_config(client):
    _admin, token = await create_admin_user()
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name="cart_agent",
            system_prompt="new prompt",
            previous_system_prompt="old prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()

    with patch("app.api.v1._admin.agent_config.create_redis_client") as mock_redis_factory:
        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        response = await client.post(
            "/api/v1/_admin/agents/config/cart_agent/rollback",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    async with async_session_maker() as session:
        result = await session.exec(
            select(AgentConfig).where(AgentConfig.agent_name == "cart_agent")
        )
        updated = result.one()
        assert updated.system_prompt == "old prompt"
        assert updated.previous_system_prompt == "new prompt"

    mock_redis.delete.assert_awaited_once_with("agent_config:cart_agent")


@pytest.mark.asyncio
async def test_rollback_agent_config_no_previous(client):
    _admin, token = await create_admin_user()
    await create_agent_config("payment_agent")

    with patch("app.api.v1._admin.agent_config.create_redis_client") as mock_redis_factory:
        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        response = await client.post(
            "/api/v1/_admin/agents/config/payment_agent/rollback",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400
    assert "no previous" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_routing_rule(client):
    _admin, token = await create_admin_user()

    response = await client.post(
        "/api/v1/_admin/agents/routing-rules",
        headers={"Authorization": f"Bearer {token}"},
        json={"intent_category": "TEST_INTENT", "target_agent": "test_agent", "priority": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent_category"] == "TEST_INTENT"
    assert data["target_agent"] == "test_agent"
    assert data["priority"] == 5


@pytest.mark.asyncio
async def test_update_routing_rule(client):
    _admin, token = await create_admin_user()
    rule = await create_routing_rule("UPDATE_INTENT", "old_agent")

    response = await client.put(
        f"/api/v1/_admin/agents/routing-rules/{rule.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_agent": "new_agent", "priority": 99},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_agent"] == "new_agent"
    assert data["priority"] == 99


@pytest.mark.asyncio
async def test_delete_routing_rule(client):
    _admin, token = await create_admin_user()
    rule = await create_routing_rule("DELETE_INTENT", "delete_agent")

    response = await client.delete(
        f"/api/v1/_admin/agents/routing-rules/{rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    async with async_session_maker() as session:
        result = await session.exec(select(RoutingRule).where(RoutingRule.id == rule.id))
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_get_agent_config_audit_log(client):
    _admin, token = await create_admin_user()
    await create_agent_config("audit_agent")

    with patch("app.api.v1._admin.agent_config.create_redis_client") as mock_redis_factory:
        mock_redis = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        response = await client.post(
            "/api/v1/_admin/agents/config/audit_agent",
            headers={"Authorization": f"Bearer {token}"},
            json={"system_prompt": "changed prompt"},
        )
        assert response.status_code == 200

    response = await client.get(
        "/api/v1/_admin/agents/config/audit_agent/audit-log",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["agent_name"] == "audit_agent"
    assert data[0]["field_name"] == "system_prompt"
