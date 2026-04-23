"""Alert monitoring Celery tasks.

Periodic tasks that evaluate system metrics against alert rules and fire
alerts when thresholds are breached.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import select

from app.celery_app import celery_app
from app.core.database import sync_session_maker
from app.models.alert import AlertEvent, AlertRule, AlertRuleStatus, AlertStatus
from app.models.observability import GraphExecutionLog

logger = logging.getLogger(__name__)


def _get_metric_value(metric: str, window_seconds: int) -> tuple[float | None, dict[str, Any]]:
    """Query the database for the current value of a metric.

    Returns:
        Tuple of (metric_value, metadata_dict). None if metric cannot be computed.
    """
    since = datetime.now(UTC) - timedelta(seconds=window_seconds)
    metadata: dict[str, Any] = {"window_seconds": window_seconds, "since": since.isoformat()}

    with sync_session_maker() as session:
        if metric == "avg_latency_ms":
            result = session.exec(
                select(func.avg(GraphExecutionLog.total_latency_ms)).where(
                    GraphExecutionLog.created_at >= since,
                    GraphExecutionLog.total_latency_ms.is_not(None),  # type: ignore
                )
            )
            val = result.one()
            return (float(val) if val is not None else None), metadata

        if metric == "error_rate":
            total_result = session.exec(
                select(func.count()).where(GraphExecutionLog.created_at >= since)
            )
            total = total_result.one() or 0
            if total == 0:
                return None, metadata

            error_result = session.exec(
                select(func.count()).where(
                    GraphExecutionLog.created_at >= since,
                    GraphExecutionLog.total_latency_ms.is_(None),  # type: ignore
                )
            )
            errors = error_result.one() or 0
            metadata.update({"total_requests": total, "error_count": errors})
            return (errors / total), metadata

        if metric == "hallucination_rate":
            total_result = session.exec(
                select(func.count()).where(
                    GraphExecutionLog.created_at >= since,
                    GraphExecutionLog.confidence_score.is_not(None),  # type: ignore
                )
            )
            total = total_result.one() or 0
            if total == 0:
                return None, metadata

            low_conf_result = session.exec(
                select(func.count()).where(
                    GraphExecutionLog.created_at >= since,
                    GraphExecutionLog.confidence_score < 0.5,  # type: ignore
                )
            )
            low_conf = low_conf_result.one() or 0
            metadata.update({"total_scored": total, "low_confidence_count": low_conf})
            return (low_conf / total), metadata

        if metric == "transfer_rate":
            total_result = session.exec(
                select(func.count()).where(GraphExecutionLog.created_at >= since)
            )
            total = total_result.one() or 0
            if total == 0:
                return None, metadata

            transfer_result = session.exec(
                select(func.count()).where(
                    GraphExecutionLog.created_at >= since,
                    GraphExecutionLog.needs_human_transfer.is_(True),  # type: ignore
                )
            )
            transfers = transfer_result.one() or 0
            metadata.update({"total_requests": total, "transfer_count": transfers})
            return (transfers / total), metadata

        if metric == "health_status":
            try:
                import urllib.request

                req = urllib.request.Request(
                    "http://localhost:8000/health",
                    method="GET",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    healthy = resp.status == 200
            except Exception as exc:
                logger.warning("Health check failed: %s", exc)
                healthy = False
            return 1.0 if healthy else 0.0, metadata

    return None, metadata


def _evaluate_operator(value: float, operator: str, threshold: float) -> bool:
    """Evaluate a metric against a threshold using the given operator."""
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "eq":
        return value == threshold
    if operator == "ne":
        return value != threshold
    logger.warning("Unknown operator: %s", operator)
    return False


def _fire_alert_sync(
    session: Any,
    rule: AlertRule,
    metric_value: float,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> AlertEvent | None:
    """Fire an alert event synchronously (for Celery tasks)."""
    import json

    event = AlertEvent(
        rule_id=rule.id,
        name=rule.name,
        severity=rule.severity,
        status=AlertStatus.FIRING,
        message=message,
        metric_value=metric_value,
        threshold=rule.threshold,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False, default=str),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    logger.warning("Alert fired: [%s] %s - %s", rule.severity.value, rule.name, message)
    return event


def _auto_resolve_cleared_alerts(session: Any) -> None:
    """Auto-resolve alerts whose conditions have cleared."""
    result = session.exec(
        select(AlertEvent).where(
            AlertEvent.status == AlertStatus.FIRING,  # type: ignore[arg-type]
            AlertEvent.rule_id.is_not(None),  # type: ignore
        )
    )
    active_events = result.all()

    for event in active_events:
        if not event.rule_id:
            continue
        rule = session.get(AlertRule, event.rule_id)
        if not rule or not rule.auto_resolve:
            continue

        current_value, _ = _get_metric_value(rule.metric, rule.duration_seconds)
        if current_value is None:
            continue

        if not _evaluate_operator(current_value, rule.operator, rule.threshold):
            event.status = AlertStatus.RESOLVED
            event.resolved_at = datetime.now(UTC)
            event.resolution_reason = "auto-resolved: condition cleared"
            session.add(event)
            logger.info("Auto-resolved alert %s (rule: %s)", event.id, rule.name)

    session.commit()


@celery_app.task(bind=True, name="alerting.evaluate_rules")
def evaluate_alert_rules(_self) -> dict:
    """Evaluate all enabled alert rules and fire alerts for breached thresholds."""
    alerts_fired = 0
    alerts_suppressed = 0
    rules_checked = 0

    with sync_session_maker() as session:
        result = session.exec(select(AlertRule).where(AlertRule.status == AlertRuleStatus.ENABLED))
        rules = list(result.all())
        rules_checked = len(rules)

        for rule in rules:
            current_value, metadata = _get_metric_value(rule.metric, rule.duration_seconds)
            if current_value is None:
                continue

            breached = _evaluate_operator(current_value, rule.operator, rule.threshold)
            if not breached:
                continue

            message = (
                f"{rule.name}: {rule.metric}={current_value:.4f} "
                f"{rule.operator} threshold={rule.threshold}"
            )

            _fire_alert_sync(
                session=session,
                rule=rule,
                metric_value=current_value,
                message=message,
                metadata=metadata,
            )
            alerts_fired += 1

        _auto_resolve_cleared_alerts(session)

    return {
        "rules_checked": rules_checked,
        "alerts_fired": alerts_fired,
        "alerts_suppressed": alerts_suppressed,
    }


@celery_app.task(bind=True, name="alerting.check_service_health")
def check_service_health(_self) -> dict:
    """Quick health check that fires a P0 alert if the service is unreachable."""
    value, metadata = _get_metric_value("health_status", 30)
    if value is None:
        return {"healthy": False, "reason": "health_check_failed"}

    healthy = value == 1.0
    if not healthy:
        with sync_session_maker() as session:
            result = session.exec(
                select(AlertRule).where(
                    AlertRule.metric == "health_status",
                    AlertRule.status == AlertRuleStatus.ENABLED,
                )
            )
            rule = result.first()
            if rule:
                _fire_alert_sync(
                    session=session,
                    rule=rule,
                    metric_value=0.0,
                    message="Service health check failed (non-200 or unreachable).",
                    metadata=metadata,
                )

    return {"healthy": healthy, "metadata": metadata}
