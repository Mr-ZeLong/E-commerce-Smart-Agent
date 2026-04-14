import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.redis import create_redis_client
from app.core.security import get_admin_user_id
from app.models.memory import AgentConfig, AgentConfigAuditLog, RoutingRule
from app.schemas.agent_config import (
    AgentConfigAuditLogResponse,
    AgentConfigListResponse,
    AgentConfigResponse,
    AgentConfigRollbackResponse,
    AgentConfigUpdateRequest,
    AgentConfigUpdateResponse,
    RoutingRuleCreateRequest,
    RoutingRuleResponse,
    RoutingRuleUpdateRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _cache_key(agent_name: str) -> str:
    return f"agent_config:{agent_name}"


async def _get_cached_config(redis, agent_name: str) -> dict | None:
    key = _cache_key(agent_name)
    data = await redis.get(key)
    if data:
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Failed to decode cached agent config for %s", agent_name)
    return None


async def _set_cached_config(redis, agent_name: str, config: AgentConfig) -> None:
    key = _cache_key(agent_name)
    data = json.dumps(
        {
            "id": config.id,
            "agent_name": config.agent_name,
            "system_prompt": config.system_prompt,
            "previous_system_prompt": config.previous_system_prompt,
            "confidence_threshold": config.confidence_threshold,
            "max_retries": config.max_retries,
            "enabled": config.enabled,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        },
        ensure_ascii=False,
    )
    await redis.setex(key, settings.AGENT_CONFIG_CACHE_TTL, data)


async def _invalidate_cached_config(redis, agent_name: str) -> None:
    key = _cache_key(agent_name)
    await redis.delete(key)


async def _log_config_change(
    session: AsyncSession,
    agent_name: str,
    changed_by: int,
    field_name: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    log = AgentConfigAuditLog(
        agent_name=agent_name,
        changed_by=changed_by,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )
    session.add(log)
    await session.flush()


@router.get("/config", response_model=AgentConfigListResponse)
async def list_agent_configs(
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List all AgentConfig and RoutingRule records."""
    result = await session.exec(select(AgentConfig).order_by(AgentConfig.agent_name))
    configs = result.all()

    rr_result = await session.exec(select(RoutingRule).order_by(desc(RoutingRule.priority)))
    routing_rules = rr_result.all()

    return AgentConfigListResponse(
        configs=[AgentConfigResponse.model_validate(c) for c in configs],
        routing_rules=[RoutingRuleResponse.model_validate(r) for r in routing_rules],
    )


@router.post("/config/{agent_name}", response_model=AgentConfigUpdateResponse)
async def update_agent_config(
    agent_name: str,
    request: AgentConfigUpdateRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Update AgentConfig fields and invalidate Redis cache."""
    result = await session.exec(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
    config = result.one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config for '{agent_name}' not found",
        )

    update_fields = request.model_dump(exclude_unset=True)
    if "system_prompt" in update_fields and update_fields["system_prompt"] is not None:
        await _log_config_change(
            session,
            agent_name,
            current_admin_id,
            "system_prompt",
            config.system_prompt,
            update_fields["system_prompt"],
        )
        config.previous_system_prompt = config.system_prompt

    for field, value in update_fields.items():
        old_value = getattr(config, field)
        if old_value != value and field != "system_prompt":
            await _log_config_change(
                session,
                agent_name,
                current_admin_id,
                field,
                str(old_value) if old_value is not None else None,
                str(value) if value is not None else None,
            )
        setattr(config, field, value)

    session.add(config)
    await session.commit()
    await session.refresh(config)

    redis = create_redis_client()
    try:
        await _invalidate_cached_config(redis, agent_name)
    finally:
        await redis.close()

    return AgentConfigUpdateResponse(
        success=True,
        agent_name=agent_name,
        message=f"Agent '{agent_name}' config updated successfully",
    )


@router.post("/config/{agent_name}/rollback", response_model=AgentConfigRollbackResponse)
async def rollback_agent_config(
    agent_name: str,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Rollback system_prompt to previous_system_prompt."""
    result = await session.exec(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
    config = result.one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config for '{agent_name}' not found",
        )

    if not config.previous_system_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No previous system prompt available for agent '{agent_name}'",
        )

    await _log_config_change(
        session,
        agent_name,
        current_admin_id,
        "system_prompt",
        config.system_prompt,
        config.previous_system_prompt,
    )

    config.previous_system_prompt, config.system_prompt = (
        config.system_prompt,
        config.previous_system_prompt,
    )

    session.add(config)
    await session.commit()
    await session.refresh(config)

    redis = create_redis_client()
    try:
        await _invalidate_cached_config(redis, agent_name)
    finally:
        await redis.close()

    return AgentConfigRollbackResponse(
        success=True,
        agent_name=agent_name,
        message=f"Agent '{agent_name}' system prompt rolled back successfully",
    )


@router.get("/config/{agent_name}/audit-log", response_model=list[AgentConfigAuditLogResponse])
async def get_agent_config_audit_log(
    agent_name: str,
    limit: int = 50,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get audit log for a given agent config."""
    result = await session.exec(
        select(AgentConfigAuditLog)
        .where(AgentConfigAuditLog.agent_name == agent_name)
        .order_by(desc(AgentConfigAuditLog.created_at))
        .limit(limit)
    )
    logs = result.all()
    return [AgentConfigAuditLogResponse.model_validate(log) for log in logs]


@router.post("/routing-rules", response_model=RoutingRuleResponse)
async def create_routing_rule(
    request: RoutingRuleCreateRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new routing rule."""
    rule = RoutingRule(
        intent_category=request.intent_category,
        target_agent=request.target_agent,
        priority=request.priority,
        condition_json=request.condition_json,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return RoutingRuleResponse.model_validate(rule)


@router.put("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def update_routing_rule(
    rule_id: int,
    request: RoutingRuleUpdateRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Update an existing routing rule."""
    result = await session.exec(select(RoutingRule).where(RoutingRule.id == rule_id))
    rule = result.one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routing rule '{rule_id}' not found",
        )

    update_fields = request.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(rule, field, value)

    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return RoutingRuleResponse.model_validate(rule)


@router.delete("/routing-rules/{rule_id}")
async def delete_routing_rule(
    rule_id: int,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete a routing rule."""
    result = await session.exec(select(RoutingRule).where(RoutingRule.id == rule_id))
    rule = result.one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routing rule '{rule_id}' not found",
        )

    await session.delete(rule)
    await session.commit()
    return {"success": True, "message": f"Routing rule '{rule_id}' deleted successfully"}
