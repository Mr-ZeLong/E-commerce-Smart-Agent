import json
import logging

from sqlmodel import desc, select

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.redis import create_redis_client
from app.models.memory import AgentConfig, RoutingRule

logger = logging.getLogger(__name__)


def _cache_key(agent_name: str) -> str:
    return f"agent_config:{agent_name}"


async def _get_cached(agent_name: str) -> dict | None:
    redis = create_redis_client()
    try:
        data = await redis.get(_cache_key(agent_name))
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Failed to decode cached agent config for %s", agent_name)
    finally:
        await redis.aclose()
    return None


async def _set_cached(agent_name: str, config: AgentConfig) -> None:
    redis = create_redis_client()
    try:
        payload = json.dumps(
            {
                "agent_name": config.agent_name,
                "system_prompt": config.system_prompt,
                "confidence_threshold": config.confidence_threshold,
                "max_retries": config.max_retries,
                "enabled": config.enabled,
            },
            ensure_ascii=False,
        )
        await redis.setex(_cache_key(agent_name), settings.AGENT_CONFIG_CACHE_TTL, payload)
    finally:
        await redis.aclose()


async def get_agent_config(agent_name: str) -> AgentConfig | None:
    cached = await _get_cached(agent_name)
    if cached:
        return AgentConfig(
            agent_name=cached["agent_name"],
            system_prompt=cached["system_prompt"],
            confidence_threshold=cached["confidence_threshold"],
            max_retries=cached["max_retries"],
            enabled=cached["enabled"],
        )

    async with async_session_maker() as session:
        result = await session.exec(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
        config = result.one_or_none()
        if config:
            await _set_cached(agent_name, config)
        return config


async def is_agent_enabled(agent_name: str) -> bool:
    config = await get_agent_config(agent_name)
    return config.enabled if config else True


async def get_effective_system_prompt(agent_name: str, fallback: str | None = None) -> str | None:
    config = await get_agent_config(agent_name)
    return config.system_prompt if config and config.system_prompt else fallback


async def get_routing_rules() -> list[RoutingRule]:
    async with async_session_maker() as session:
        result = await session.exec(select(RoutingRule).order_by(desc(RoutingRule.priority)))
        return list(result.all())


async def get_target_agent_for_intent(intent_category: str, fallback: str = "policy_agent") -> str:
    rules = await get_routing_rules()
    for rule in rules:
        if rule.intent_category.upper() == intent_category.upper():
            return rule.target_agent
    return fallback
