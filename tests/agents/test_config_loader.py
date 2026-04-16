import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import config_loader
from app.models.memory import AgentConfig, RoutingRule


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.exec = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_agent_config_cache_miss_db_hit(mock_redis, mock_session):
    mock_redis.get.return_value = None

    config = AgentConfig(
        agent_name="product",
        system_prompt="You are a product agent.",
        confidence_threshold=0.7,
        max_retries=3,
        enabled=True,
    )
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = config
    mock_session.exec.return_value = result_mock

    with (
        patch("app.agents.config_loader.create_redis_client", return_value=mock_redis),
        patch("app.agents.config_loader.async_session_maker") as mock_maker,
    ):
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        got = await config_loader.get_agent_config("product")

    assert got is not None
    assert got.agent_name == "product"
    assert got.system_prompt == "You are a product agent."
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_get_agent_config_cache_hit(mock_redis):
    cached = json.dumps(
        {
            "agent_name": "order_agent",
            "system_prompt": "order prompt",
            "confidence_threshold": 0.8,
            "max_retries": 2,
            "enabled": False,
        },
        ensure_ascii=False,
    )
    mock_redis.get.return_value = cached

    with patch("app.agents.config_loader.create_redis_client", return_value=mock_redis):
        got = await config_loader.get_agent_config("order_agent")

    assert got is not None
    assert got.agent_name == "order_agent"
    assert got.enabled is False
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_is_agent_enabled_default_when_missing(mock_redis):
    mock_redis.get.return_value = None

    mock_session = AsyncMock()
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    mock_session.exec.return_value = result_mock

    with (
        patch("app.agents.config_loader.create_redis_client", return_value=mock_redis),
        patch("app.agents.config_loader.async_session_maker") as mock_maker,
    ):
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await config_loader.is_agent_enabled("unknown_agent") is True


@pytest.mark.asyncio
async def test_get_effective_system_prompt_fallback(mock_redis):
    mock_redis.get.return_value = None

    mock_session = AsyncMock()
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    mock_session.exec.return_value = result_mock

    with (
        patch("app.agents.config_loader.create_redis_client", return_value=mock_redis),
        patch("app.agents.config_loader.async_session_maker") as mock_maker,
    ):
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        prompt = await config_loader.get_effective_system_prompt(
            "unknown_agent", fallback="default prompt"
        )

    assert prompt == "default prompt"


@pytest.mark.asyncio
async def test_get_routing_rules(mock_session):
    rules = [
        RoutingRule(intent_category="ORDER", target_agent="order_agent", priority=10),
        RoutingRule(intent_category="POLICY", target_agent="policy_agent", priority=5),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = rules
    mock_session.exec.return_value = result_mock

    with patch("app.agents.config_loader.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        got = await config_loader.get_routing_rules()

    assert len(got) == 2
    assert got[0].intent_category == "ORDER"


@pytest.mark.asyncio
async def test_get_target_agent_for_intent_matches_rule(mock_session):
    rules = [
        RoutingRule(intent_category="ORDER", target_agent="order_agent", priority=10),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = rules
    mock_session.exec.return_value = result_mock

    with patch("app.agents.config_loader.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        target = await config_loader.get_target_agent_for_intent("ORDER")

    assert target == "order_agent"


@pytest.mark.asyncio
async def test_get_target_agent_for_intent_fallback(mock_session):
    result_mock = MagicMock()
    result_mock.all.return_value = []
    mock_session.exec.return_value = result_mock

    with patch("app.agents.config_loader.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        target = await config_loader.get_target_agent_for_intent("UNKNOWN")

    assert target == "policy_agent"


@pytest.mark.asyncio
async def test_cached_invalid_json_logs_warning(mock_redis, caplog):
    mock_redis.get.return_value = "not valid json"

    with (
        patch("app.agents.config_loader.create_redis_client", return_value=mock_redis),
        caplog.at_level("WARNING"),
    ):
        result = await config_loader._get_cached("some_agent")

    assert result is None
    assert "Failed to decode" in caplog.text
