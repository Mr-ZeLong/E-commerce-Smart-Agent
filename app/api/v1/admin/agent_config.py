import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.redis import create_redis_client
from app.core.security import get_admin_user_id
from app.models.memory import AgentConfig, AgentConfigAuditLog, AgentConfigVersion, RoutingRule
from app.models.multi_intent_log import MultiIntentDecisionLog
from app.models.prompt_effect_report import PromptEffectReport
from app.schemas.agent_config import (
    AgentConfigAuditLogResponse,
    AgentConfigListResponse,
    AgentConfigResponse,
    AgentConfigRollbackResponse,
    AgentConfigUpdateRequest,
    AgentConfigUpdateResponse,
    AgentConfigVersionMetricsResponse,
    AgentConfigVersionResponse,
    MultiIntentDecisionLogLabelRequest,
    MultiIntentDecisionLogResponse,
    PromptEffectReportResponse,
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


async def _create_version_snapshot(
    session: AsyncSession,
    agent_name: str,
    changed_by: int,
    config: AgentConfig,
) -> None:
    snapshot = AgentConfigVersion(
        agent_name=agent_name,
        changed_by=changed_by,
        system_prompt=config.system_prompt,
        confidence_threshold=config.confidence_threshold,
        max_retries=config.max_retries,
        enabled=config.enabled,
    )
    session.add(snapshot)
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

    if update_fields:
        await _create_version_snapshot(session, agent_name, current_admin_id, config)

    session.add(config)
    await session.commit()
    await session.refresh(config)

    redis = create_redis_client()
    try:
        await _invalidate_cached_config(redis, agent_name)
    finally:
        await redis.aclose()

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

    await _create_version_snapshot(session, agent_name, current_admin_id, config)

    session.add(config)
    await session.commit()
    await session.refresh(config)

    redis = create_redis_client()
    try:
        await _invalidate_cached_config(redis, agent_name)
    finally:
        await redis.aclose()

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


@router.get("/config/{agent_name}/versions", response_model=list[AgentConfigVersionResponse])
async def get_agent_config_versions(
    agent_name: str,
    limit: int = 50,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get version history for a given agent config."""
    result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_name == agent_name)
        .order_by(desc(AgentConfigVersion.created_at))
        .limit(limit)
    )
    versions = result.all()
    return [AgentConfigVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/config/{agent_name}/versions/{version_id}/rollback",
    response_model=AgentConfigRollbackResponse,
)
async def rollback_agent_config_to_version(
    agent_name: str,
    version_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Rollback agent config to a specific version snapshot."""
    config_result = await session.exec(
        select(AgentConfig).where(AgentConfig.agent_name == agent_name)
    )
    config = config_result.one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config for '{agent_name}' not found",
        )

    version_result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.id == version_id)
        .where(AgentConfigVersion.agent_name == agent_name)
    )
    version = version_result.one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version_id}' not found for agent '{agent_name}'",
        )

    await _log_config_change(
        session,
        agent_name,
        current_admin_id,
        "system_prompt",
        config.system_prompt,
        version.system_prompt,
    )

    config.system_prompt = version.system_prompt
    config.confidence_threshold = version.confidence_threshold
    config.max_retries = version.max_retries
    config.enabled = version.enabled
    config.previous_system_prompt = version.system_prompt

    await _create_version_snapshot(session, agent_name, current_admin_id, config)

    session.add(config)
    await session.commit()
    await session.refresh(config)

    redis = create_redis_client()
    try:
        await _invalidate_cached_config(redis, agent_name)
    finally:
        await redis.aclose()

    return AgentConfigRollbackResponse(
        success=True,
        agent_name=agent_name,
        message=f"Agent '{agent_name}' rolled back to version {version_id} successfully",
    )


@router.get(
    "/config/{agent_name}/versions/{version_id}/metrics",
    response_model=AgentConfigVersionMetricsResponse,
)
async def get_agent_config_version_metrics(
    agent_name: str,
    version_id: int,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get execution metrics for a given agent config version time window."""
    from sqlalchemy import text

    version_result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.id == version_id)
        .where(AgentConfigVersion.agent_name == agent_name)
    )
    version = version_result.one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version_id}' not found for agent '{agent_name}'",
        )

    next_version_result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_name == agent_name)
        .where(AgentConfigVersion.created_at > version.created_at)
        .order_by(AgentConfigVersion.created_at.asc())  # type: ignore
        .limit(1)
    )
    next_version = next_version_result.one_or_none()
    end_time = next_version.created_at if next_version else None

    stmt = """
        SELECT
            COUNT(*) AS total_sessions,
            AVG(confidence_score) AS avg_confidence,
            SUM(CASE WHEN needs_human_transfer THEN 1 ELSE 0 END) AS transfer_count,
            AVG(total_latency_ms) AS avg_latency_ms
        FROM graph_execution_logs
        WHERE final_agent = :agent_name
        AND created_at >= :start_time
    """
    params: dict = {"agent_name": agent_name, "start_time": version.created_at}
    if end_time:
        stmt += " AND created_at < :end_time"
        params["end_time"] = end_time

    result = await session.execute(text(stmt).bindparams(**params))  # type: ignore
    row = result.mappings().one()

    total = int(row["total_sessions"] or 0)
    avg_conf = float(row["avg_confidence"]) if row["avg_confidence"] is not None else None
    transfers = int(row["transfer_count"] or 0)
    avg_latency = float(row["avg_latency_ms"]) if row["avg_latency_ms"] is not None else None

    return AgentConfigVersionMetricsResponse(
        total_sessions=total,
        avg_confidence=round(avg_conf, 4) if avg_conf is not None else None,
        transfer_rate=round(transfers / total, 4) if total else 0.0,
        avg_latency_ms=round(avg_latency, 2) if avg_latency is not None else None,
    )


@router.get(
    "/config/{agent_name}/reports",
    response_model=list[PromptEffectReportResponse],
)
async def get_agent_config_reports(
    agent_name: str,
    limit: int = 12,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(PromptEffectReport)
        .where(PromptEffectReport.agent_name == agent_name)
        .order_by(desc(PromptEffectReport.report_month))
        .limit(limit)
    )
    reports = result.all()
    return [PromptEffectReportResponse.model_validate(r) for r in reports]


@router.post("/config/{agent_name}/reports/generate")
async def trigger_agent_config_report(
    agent_name: str,
    report_month: str,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    from app.tasks.prompt_effect_tasks import generate_monthly_report

    config_result = await session.exec(
        select(AgentConfig).where(AgentConfig.agent_name == agent_name)
    )
    if not config_result.one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config for '{agent_name}' not found",
        )

    task_result = generate_monthly_report.delay(agent_name, report_month)
    return {"task_id": task_result.id, "agent_name": agent_name, "report_month": report_month}


@router.post("/config/{agent_name}/evaluate-few-shot")
async def evaluate_few_shot(
    agent_name: str,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    from app.tasks.evaluation_tasks import run_few_shot_evaluation

    config_result = await session.exec(
        select(AgentConfig).where(AgentConfig.agent_name == agent_name)
    )
    if not config_result.one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent config for '{agent_name}' not found",
        )

    task_result = run_few_shot_evaluation.delay()
    return {"task_id": task_result.id, "agent_name": agent_name, "status": "queued"}


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


@router.post(
    "/multi-intent-decisions/{decision_id}/label",
    response_model=MultiIntentDecisionLogResponse,
)
async def label_multi_intent_decision(
    decision_id: int,
    request: MultiIntentDecisionLogLabelRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Submit a human label for a multi-intent decision log entry."""
    result = await session.exec(
        select(MultiIntentDecisionLog).where(MultiIntentDecisionLog.id == decision_id)
    )
    log = result.one_or_none()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision log '{decision_id}' not found",
        )

    log.human_label = request.human_label
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return MultiIntentDecisionLogResponse.model_validate(log)
