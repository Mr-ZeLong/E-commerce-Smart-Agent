import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.memory import AgentConfig, RoutingRule
from app.models.observability import GraphExecutionLog
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
    agent_name = f"policy_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)
    await create_routing_rule("POLICY", agent_name)

    response = await client.get(
        "/api/v1/admin/agents/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "configs" in data
    assert "routing_rules" in data
    agent_names = [c["agent_name"] for c in data["configs"]]
    assert agent_name in agent_names
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
        "/api/v1/admin/agents/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_agent_config(client, redis_client):
    _admin, token = await create_admin_user()
    agent_name = f"order_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    cache_key = f"agent_config:{agent_name}"
    await redis_client.set(cache_key, "cached_value")

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "updated prompt", "confidence_threshold": 0.8},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated" in data["message"].lower() or "success" in data["message"].lower()

    async with async_session_maker() as session:
        result = await session.exec(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
        updated = result.one()
        assert updated.system_prompt == "updated prompt"
        assert updated.previous_system_prompt == "original prompt"
        assert updated.confidence_threshold == 0.8

    cached = await redis_client.get(cache_key)
    assert cached is None


@pytest.mark.asyncio
async def test_update_agent_config_not_found(client):
    _admin, token = await create_admin_user()

    response = await client.post(
        "/api/v1/admin/agents/config/nonexistent_agent",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "prompt"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rollback_agent_config(client, redis_client):
    _admin, token = await create_admin_user()
    agent_name = f"cart_agent_{uuid.uuid4().hex[:8]}"
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="new prompt",
            previous_system_prompt="old prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()

    cache_key = f"agent_config:{agent_name}"
    await redis_client.set(cache_key, "cached_value")

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}/rollback",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    async with async_session_maker() as session:
        result = await session.exec(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
        updated = result.one()
        assert updated.system_prompt == "old prompt"
        assert updated.previous_system_prompt == "new prompt"

    cached = await redis_client.get(cache_key)
    assert cached is None


@pytest.mark.asyncio
async def test_rollback_agent_config_no_previous(client):
    _admin, token = await create_admin_user()
    agent_name = f"payment_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}/rollback",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "no previous" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_routing_rule(client):
    _admin, token = await create_admin_user()

    response = await client.post(
        "/api/v1/admin/agents/routing-rules",
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
        f"/api/v1/admin/agents/routing-rules/{rule.id}",
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
        f"/api/v1/admin/agents/routing-rules/{rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

    async with async_session_maker() as session:
        result = await session.exec(select(RoutingRule).where(RoutingRule.id == rule.id))
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_get_agent_config_audit_log(client, redis_client):
    _admin, token = await create_admin_user()
    agent_name = f"audit_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    cache_key = f"agent_config:{agent_name}"
    await redis_client.set(cache_key, "cached_value")

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "changed prompt"},
    )
    assert response.status_code == 200

    cached = await redis_client.get(cache_key)
    assert cached is None

    response = await client.get(
        f"/api/v1/admin/agents/config/{agent_name}/audit-log",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["agent_name"] == agent_name
    assert data[0]["field_name"] == "system_prompt"


@pytest.mark.asyncio
async def test_get_agent_config_versions(client):
    _admin, token = await create_admin_user()
    agent_name = f"version_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "updated prompt"},
    )
    assert response.status_code == 200

    response = await client.get(
        f"/api/v1/admin/agents/config/{agent_name}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["agent_name"] == agent_name
    assert data[0]["system_prompt"] == "updated prompt"


@pytest.mark.asyncio
async def test_rollback_agent_config_to_version(client, redis_client):
    _admin, token = await create_admin_user()
    agent_name = f"rollback_version_agent_{uuid.uuid4().hex[:8]}"
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="current prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "updated prompt"},
    )
    assert response.status_code == 200

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "third prompt"},
    )
    assert response.status_code == 200

    versions_response = await client.get(
        f"/api/v1/admin/agents/config/{agent_name}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    versions = versions_response.json()
    assert len(versions) >= 2
    first_version_id = versions[0]["id"]

    cache_key = f"agent_config:{agent_name}"
    await redis_client.set(cache_key, "cached_value")

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}/versions/{first_version_id}/rollback",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    async with async_session_maker() as session:
        result = await session.exec(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
        updated = result.one()
        assert updated.system_prompt == "third prompt"

    cached = await redis_client.get(cache_key)
    assert cached is None


@pytest.mark.asyncio
async def test_get_agent_config_version_metrics(client):
    _admin, token = await create_admin_user()
    agent_name = f"metrics_agent_{uuid.uuid4().hex[:8]}"
    async with async_session_maker() as session:
        config = AgentConfig(
            agent_name=agent_name,
            system_prompt="prompt",
            confidence_threshold=0.7,
            max_retries=3,
            enabled=True,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)

    response = await client.post(
        f"/api/v1/admin/agents/config/{agent_name}",
        headers={"Authorization": f"Bearer {token}"},
        json={"system_prompt": "updated prompt"},
    )
    assert response.status_code == 200

    versions_response = await client.get(
        f"/api/v1/admin/agents/config/{agent_name}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    versions = versions_response.json()
    version_id = versions[0]["id"]

    async with async_session_maker() as session:
        log = GraphExecutionLog(
            thread_id="t1",
            user_id=_admin.id or 0,
            final_agent=agent_name,
            confidence_score=0.85,
            needs_human_transfer=False,
            total_latency_ms=120,
        )
        session.add(log)
        await session.commit()

    response = await client.get(
        f"/api/v1/admin/agents/config/{agent_name}/versions/{version_id}/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_sessions"] == 1
    assert data["avg_confidence"] == 0.85
    assert data["transfer_rate"] == 0.0


@pytest.mark.asyncio
async def test_evaluate_few_shot_endpoint(client):
    _admin, token = await create_admin_user()
    agent_name = f"few_shot_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    with patch("app.tasks.evaluation_tasks.run_few_shot_evaluation") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-123")
        response = await client.post(
            f"/api/v1/admin/agents/config/{agent_name}/evaluate-few-shot",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_name"] == agent_name
        assert data["status"] == "queued"
        assert data["task_id"] == "task-123"
        mock_task.delay.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_agent_config_reports(client):
    _admin, token = await create_admin_user()
    agent_name = f"report_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    async with async_session_maker() as session:
        from app.models.prompt_effect_report import PromptEffectReport

        report = PromptEffectReport(
            report_month="2026-03",
            agent_name=agent_name,
            total_sessions=100,
            transfer_rate=0.05,
            avg_confidence=0.92,
            avg_latency_ms=150.0,
        )
        session.add(report)
        await session.commit()

    response = await client.get(
        f"/api/v1/admin/agents/config/{agent_name}/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["report_month"] == "2026-03"
    assert data[0]["agent_name"] == agent_name
    assert data[0]["total_sessions"] == 100


@pytest.mark.asyncio
async def test_trigger_agent_config_report(client):
    _admin, token = await create_admin_user()
    agent_name = f"trigger_report_agent_{uuid.uuid4().hex[:8]}"
    await create_agent_config(agent_name)

    with patch("app.tasks.prompt_effect_tasks.generate_monthly_report") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-456")
        response = await client.post(
            f"/api/v1/admin/agents/config/{agent_name}/reports/generate?report_month=2026-03",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_name"] == agent_name
        assert data["report_month"] == "2026-03"
        assert data["task_id"] == "task-456"
        mock_task.delay.assert_called_once_with(agent_name, "2026-03")


@pytest.mark.asyncio
async def test_label_multi_intent_decision(client):
    _admin, token = await create_admin_user()
    from app.models.multi_intent_log import MultiIntentDecisionLog

    async with async_session_maker() as session:
        log = MultiIntentDecisionLog(
            query="test query",
            intent_a="ORDER",
            intent_b="POLICY",
            rule_based_result=True,
            llm_result=True,
            llm_reason="test",
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        decision_id = log.id

    response = await client.post(
        f"/api/v1/admin/agents/multi-intent-decisions/{decision_id}/label",
        headers={"Authorization": f"Bearer {token}"},
        json={"human_label": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == decision_id
    assert data["human_label"] is False

    async with async_session_maker() as session:
        result = await session.exec(
            select(MultiIntentDecisionLog).where(MultiIntentDecisionLog.id == decision_id)
        )
        updated = result.one()
        assert updated.human_label is False

    async with async_session_maker() as session:
        result = await session.exec(
            select(MultiIntentDecisionLog).where(MultiIntentDecisionLog.id == decision_id)
        )
        log = result.one()
        await session.delete(log)
        await session.commit()
