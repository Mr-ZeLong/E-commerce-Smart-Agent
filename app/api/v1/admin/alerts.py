"""Alert management admin API routes.

Provides CRUD operations for alert rules and lifecycle management for alert events.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Request as FastAPIRequest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.alert import (
    AlertEvent,
    AlertNotification,
    AlertRule,
    AlertRuleStatus,
    AlertSeverity,
    AlertStatus,
)
from app.schemas.admin import (
    AlertAcknowledgeRequest,
    AlertEventListResponse,
    AlertEventResponse,
    AlertNotificationResponse,
    AlertResolveRequest,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
)
from app.services.alert_service import AlertService

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_channels(channels_str: str) -> list[dict[str, Any]]:
    try:
        return json.loads(channels_str)
    except json.JSONDecodeError:
        return []


def _rule_to_response(rule: AlertRule) -> AlertRuleResponse:
    assert rule.id is not None, "Rule ID must not be None"
    return AlertRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        metric=rule.metric,
        operator=rule.operator,
        threshold=rule.threshold,
        duration_seconds=rule.duration_seconds,
        severity=rule.severity.value,
        status=rule.status.value,
        channels=_parse_channels(rule.channels),
        suppress_interval_seconds=rule.suppress_interval_seconds,
        auto_resolve=rule.auto_resolve,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
    )


def _event_to_response(event: AlertEvent) -> AlertEventResponse:
    assert event.id is not None, "Event ID must not be None"
    return AlertEventResponse(
        id=event.id,
        rule_id=event.rule_id,
        name=event.name,
        severity=event.severity.value,
        status=event.status.value,
        message=event.message,
        metric_value=event.metric_value,
        threshold=event.threshold,
        metadata_json=json.loads(event.metadata_json) if event.metadata_json else None,
        fired_at=event.fired_at.isoformat(),
        acknowledged_at=event.acknowledged_at.isoformat() if event.acknowledged_at else None,
        acknowledged_by=event.acknowledged_by,
        resolved_at=event.resolved_at.isoformat() if event.resolved_at else None,
        resolved_by=event.resolved_by,
        resolution_reason=event.resolution_reason,
    )


def _notification_to_response(notification: AlertNotification) -> AlertNotificationResponse:
    assert notification.id is not None, "Notification ID must not be None"
    return AlertNotificationResponse(
        id=notification.id,
        alert_event_id=notification.alert_event_id,
        channel=notification.channel.value,
        destination=notification.destination,
        sent_at=notification.sent_at.isoformat(),
        success=notification.success,
        response_status=notification.response_status,
        response_body=notification.response_body,
    )


@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    fastapi_request: FastAPIRequest,
    status: str | None = None,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List all alert rules, optionally filtered by status."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    rule_status = AlertRuleStatus(status) if status else None
    rules = await service.get_rules(session, status=rule_status)
    return [_rule_to_response(rule) for rule in rules]


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    fastapi_request: FastAPIRequest,
    request: AlertRuleCreateRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new alert rule."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    try:
        severity = AlertSeverity(request.severity)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity: {request.severity}. Must be one of: P0, P1, P2",
        ) from exc

    rule = await service.create_rule(
        session=session,
        name=request.name,
        metric=request.metric,
        operator=request.operator,
        threshold=request.threshold,
        severity=severity,
        description=request.description,
        duration_seconds=request.duration_seconds,
        channels=request.channels,
        suppress_interval_seconds=request.suppress_interval_seconds,
        auto_resolve=request.auto_resolve,
    )
    return _rule_to_response(rule)


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: int,
    fastapi_request: FastAPIRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get a single alert rule by ID."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    rule = await service.get_rule(session, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule '{rule_id}' not found",
        )
    return _rule_to_response(rule)


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    fastapi_request: FastAPIRequest,
    request: AlertRuleUpdateRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Update an existing alert rule."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    updates = request.model_dump(exclude_unset=True)

    if "severity" in updates:
        try:
            updates["severity"] = AlertSeverity(updates["severity"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {updates['severity']}. Must be one of: P0, P1, P2",
            ) from exc

    if "status" in updates:
        try:
            updates["status"] = AlertRuleStatus(updates["status"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {updates['status']}. Must be one of: enabled, disabled",
            ) from exc

    rule = await service.update_rule(session, rule_id, updates)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule '{rule_id}' not found",
        )
    return _rule_to_response(rule)


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    fastapi_request: FastAPIRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete an alert rule."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    success = await service.delete_rule(session, rule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule '{rule_id}' not found",
        )
    return {"success": True, "message": f"Alert rule '{rule_id}' deleted"}


@router.get("/events", response_model=AlertEventListResponse)
async def list_alert_events(
    fastapi_request: FastAPIRequest,
    status: str | None = None,
    severity: str | None = None,
    since_hours: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List alert events with optional filters."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)

    event_status = AlertStatus(status) if status else None
    event_severity = AlertSeverity(severity) if severity else None
    since = datetime.now(UTC) - timedelta(hours=since_hours) if since_hours else None

    events, total = await service.get_events(
        session,
        status=event_status,
        severity=event_severity,
        since=since,
        limit=limit,
        offset=offset,
    )
    return AlertEventListResponse(
        events=[_event_to_response(event) for event in events],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/events/active", response_model=list[AlertEventResponse])
async def get_active_alert_events(
    fastapi_request: FastAPIRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get all currently firing or acknowledged alerts."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    events = await service.get_active_events(session)
    return [_event_to_response(event) for event in events]


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventResponse)
async def acknowledge_alert_event(
    event_id: int,
    fastapi_request: FastAPIRequest,
    request: AlertAcknowledgeRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Acknowledge an alert event."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    event = await service.acknowledge_alert(session, event_id, request.user_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert event '{event_id}' not found or already resolved",
        )
    return _event_to_response(event)


@router.post("/events/{event_id}/resolve", response_model=AlertEventResponse)
async def resolve_alert_event(
    event_id: int,
    fastapi_request: FastAPIRequest,
    request: AlertResolveRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Resolve an alert event."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    event = await service.resolve_alert(
        session, event_id, user_id=request.user_id, reason=request.reason
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert event '{event_id}' not found or already resolved",
        )
    return _event_to_response(event)


@router.get("/events/{event_id}/notifications", response_model=list[AlertNotificationResponse])
async def get_alert_event_notifications(
    event_id: int,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get notification history for an alert event."""
    result = await session.exec(
        select(AlertNotification)
        .where(AlertNotification.alert_event_id == event_id)
        .order_by(AlertNotification.sent_at.desc())  # type: ignore
    )
    notifications = list(result.all())
    return [_notification_to_response(n) for n in notifications]


@router.post("/rules/ensure-defaults")
async def ensure_default_alert_rules(
    fastapi_request: FastAPIRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Ensure default alert rules exist in the database."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    await service.ensure_default_rules(session)
    return {"success": True, "message": "Default alert rules ensured"}


@router.post("/trigger", response_model=AlertEventResponse)
async def manual_trigger_alert(
    rule_id: int,
    fastapi_request: FastAPIRequest,
    metric_value: float | None = None,
    message: str | None = None,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger an alert for a given rule."""
    service = AlertService(redis=fastapi_request.app.state.redis_client)
    rule = await service.get_rule(session, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert rule '{rule_id}' not found",
        )

    actual_metric = metric_value if metric_value is not None else rule.threshold
    actual_message = message or f"Manually triggered alert for rule '{rule.name}'"

    event = await service.fire_alert(
        session=session,
        rule=rule,
        metric_value=actual_metric,
        message=actual_message,
        metadata={"triggered_by": "manual", "admin_id": _current_admin_id},
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Alert suppressed by deduplication rules",
        )
    return _event_to_response(event)
