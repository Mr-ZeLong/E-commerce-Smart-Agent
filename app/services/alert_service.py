"""Alert service for the E-commerce Smart Agent.

Provides persistent alert management with email, webhook, PagerDuty, and OpsGenie
integrations. Includes suppression, deduplication, and SLA tracking.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import redis.asyncio as aioredis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.email import send_email
from app.models.alert import (
    AlertChannel,
    AlertEvent,
    AlertNotification,
    AlertRule,
    AlertRuleStatus,
    AlertSeverity,
    AlertStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "name": "high_latency",
        "description": "End-to-end chat latency exceeds threshold.",
        "metric": "avg_latency_ms",
        "operator": "gt",
        "threshold": 2000.0,
        "duration_seconds": 120,
        "severity": AlertSeverity.P1,
        "suppress_interval_seconds": 300,
        "auto_resolve": True,
    },
    {
        "name": "high_error_rate",
        "description": "Chat error rate exceeds 1%.",
        "metric": "error_rate",
        "operator": "gt",
        "threshold": 0.01,
        "duration_seconds": 120,
        "severity": AlertSeverity.P0,
        "suppress_interval_seconds": 300,
        "auto_resolve": True,
    },
    {
        "name": "high_hallucination_rate",
        "description": "Hallucination rate exceeds 5%.",
        "metric": "hallucination_rate",
        "operator": "gt",
        "threshold": 0.05,
        "duration_seconds": 300,
        "severity": AlertSeverity.P1,
        "suppress_interval_seconds": 600,
        "auto_resolve": True,
    },
    {
        "name": "service_unavailable",
        "description": "Health check endpoint returns non-200 status.",
        "metric": "health_status",
        "operator": "eq",
        "threshold": 0.0,
        "duration_seconds": 60,
        "severity": AlertSeverity.P0,
        "suppress_interval_seconds": 60,
        "auto_resolve": True,
    },
    {
        "name": "high_transfer_rate",
        "description": "Human transfer rate exceeds threshold.",
        "metric": "transfer_rate",
        "operator": "gt",
        "threshold": 0.3,
        "duration_seconds": 300,
        "severity": AlertSeverity.P1,
        "suppress_interval_seconds": 300,
        "auto_resolve": True,
    },
    {
        "name": "low_confidence",
        "description": "Median confidence score below threshold.",
        "metric": "confidence_score",
        "operator": "lt",
        "threshold": 0.6,
        "duration_seconds": 300,
        "severity": AlertSeverity.P1,
        "suppress_interval_seconds": 300,
        "auto_resolve": True,
    },
]


class AlertService:
    """Service for managing alert rules, events, and notifications."""

    def __init__(self, redis: aioredis.Redis | None = None) -> None:
        self._redis = redis
        self._suppression_cache: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def ensure_default_rules(self, session: AsyncSession) -> None:
        """Create default alert rules if none exist."""
        result = await session.exec(select(AlertRule))
        existing = result.all()
        if existing:
            return

        for rule_data in _DEFAULT_RULES:
            rule = AlertRule(
                name=rule_data["name"],
                description=rule_data.get("description"),
                metric=rule_data["metric"],
                operator=rule_data["operator"],
                threshold=rule_data["threshold"],
                duration_seconds=rule_data["duration_seconds"],
                severity=rule_data["severity"],
                status=AlertRuleStatus.ENABLED,
                channels=json.dumps([{"channel": "email", "destination": None}]),
                suppress_interval_seconds=rule_data["suppress_interval_seconds"],
                auto_resolve=rule_data["auto_resolve"],
            )
            session.add(rule)
        await session.commit()
        logger.info("Created %d default alert rules", len(_DEFAULT_RULES))

    async def create_rule(
        self,
        session: AsyncSession,
        name: str,
        metric: str,
        operator: str,
        threshold: float,
        severity: AlertSeverity,
        description: str | None = None,
        duration_seconds: int = 60,
        channels: list[dict[str, Any]] | None = None,
        suppress_interval_seconds: int = 300,
        auto_resolve: bool = True,
    ) -> AlertRule:
        """Create a new alert rule."""
        rule = AlertRule(
            name=name,
            description=description,
            metric=metric,
            operator=operator,
            threshold=threshold,
            duration_seconds=duration_seconds,
            severity=severity,
            status=AlertRuleStatus.ENABLED,
            channels=json.dumps(channels or [{"channel": "email", "destination": None}]),
            suppress_interval_seconds=suppress_interval_seconds,
            auto_resolve=auto_resolve,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    async def update_rule(
        self,
        session: AsyncSession,
        rule_id: int,
        updates: dict[str, Any],
    ) -> AlertRule | None:
        """Update an existing alert rule."""
        rule = await session.get(AlertRule, rule_id)
        if not rule:
            return None

        allowed = {
            "name",
            "description",
            "metric",
            "operator",
            "threshold",
            "duration_seconds",
            "severity",
            "status",
            "channels",
            "suppress_interval_seconds",
            "auto_resolve",
        }
        for key, value in updates.items():
            if key in allowed:
                if key == "channels" and isinstance(value, list):
                    value = json.dumps(value)
                setattr(rule, key, value)

        await session.commit()
        await session.refresh(rule)
        return rule

    async def delete_rule(self, session: AsyncSession, rule_id: int) -> bool:
        """Delete an alert rule and its associated events."""
        rule = await session.get(AlertRule, rule_id)
        if not rule:
            return False

        await session.delete(rule)
        await session.commit()
        return True

    async def get_rules(
        self,
        session: AsyncSession,
        status: AlertRuleStatus | None = None,
    ) -> list[AlertRule]:
        """List alert rules, optionally filtered by status."""
        stmt = select(AlertRule)
        if status is not None:
            stmt = stmt.where(AlertRule.status == status)
        stmt = stmt.order_by(AlertRule.created_at.desc())  # type: ignore
        result = await session.exec(stmt)
        return list(result.all())

    async def get_rule(self, session: AsyncSession, rule_id: int) -> AlertRule | None:
        """Get a single alert rule by ID."""
        return await session.get(AlertRule, rule_id)

    async def fire_alert(
        self,
        session: AsyncSession,
        rule: AlertRule,
        metric_value: float,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> AlertEvent | None:
        """Fire an alert event if not suppressed."""
        cache_key = f"alert:suppressed:{rule.id}:{rule.name}"
        now = datetime.now(UTC)

        # Check suppression outside the lock to avoid blocking on Redis I/O.
        suppressed = False
        if self._redis is not None:
            try:
                last_fired_raw = await self._redis.get(cache_key)
                if last_fired_raw:
                    try:
                        last_fired = datetime.fromisoformat(last_fired_raw)
                    except ValueError:
                        last_fired = None
                    if (
                        last_fired
                        and (now - last_fired).total_seconds() < rule.suppress_interval_seconds
                    ):
                        suppressed = True
            except aioredis.RedisError:
                # Redis read failed—treat as not suppressed and fall back to memory.
                pass

        if not suppressed:
            async with self._lock:
                last_fired = self._suppression_cache.get(cache_key)
                if (
                    last_fired
                    and (now - last_fired).total_seconds() < rule.suppress_interval_seconds
                ):
                    suppressed = True

        if suppressed:
            logger.debug("Alert %s suppressed", rule.name)
            return None

        if self._redis is not None:
            try:
                await self._redis.setex(
                    cache_key,
                    rule.suppress_interval_seconds,
                    now.isoformat(),
                )
            except aioredis.RedisError:
                # Redis write failed—fall back to in-memory cache.
                async with self._lock:
                    self._suppression_cache[cache_key] = now
        else:
            async with self._lock:
                self._suppression_cache[cache_key] = now

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
        await session.commit()
        await session.refresh(event)

        await self._notify(session, event, rule)
        logger.warning("Alert fired: [%s] %s - %s", rule.severity.value, rule.name, message)
        return event

    async def acknowledge_alert(
        self,
        session: AsyncSession,
        event_id: int,
        user_id: int,
    ) -> AlertEvent | None:
        """Acknowledge an alert event."""
        event = await session.get(AlertEvent, event_id)
        if not event or event.status != AlertStatus.FIRING:
            return None

        event.status = AlertStatus.ACKNOWLEDGED
        event.acknowledged_at = datetime.now(UTC)
        event.acknowledged_by = user_id
        await session.commit()
        await session.refresh(event)
        return event

    async def resolve_alert(
        self,
        session: AsyncSession,
        event_id: int,
        user_id: int | None = None,
        reason: str | None = None,
    ) -> AlertEvent | None:
        """Resolve an alert event."""
        event = await session.get(AlertEvent, event_id)
        if not event or event.status == AlertStatus.RESOLVED:
            return None

        event.status = AlertStatus.RESOLVED
        event.resolved_at = datetime.now(UTC)
        event.resolved_by = user_id
        event.resolution_reason = reason
        await session.commit()
        await session.refresh(event)
        return event

    async def get_events(
        self,
        session: AsyncSession,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AlertEvent], int]:
        """Query alert events with optional filters."""
        stmt = select(AlertEvent)
        count_stmt = select(AlertEvent)

        if status is not None:
            stmt = stmt.where(AlertEvent.status == status)
            count_stmt = count_stmt.where(AlertEvent.status == status)
        if severity is not None:
            stmt = stmt.where(AlertEvent.severity == severity)
            count_stmt = count_stmt.where(AlertEvent.severity == severity)
        if since is not None:
            stmt = stmt.where(AlertEvent.fired_at >= since)
            count_stmt = count_stmt.where(AlertEvent.fired_at >= since)

        stmt = stmt.order_by(AlertEvent.fired_at.desc()).offset(offset).limit(limit)  # type: ignore

        result = await session.exec(stmt)
        events = list(result.all())

        count_result = await session.exec(count_stmt)  # type: ignore[arg-type]
        total = len(count_result.all())

        return events, total

    async def get_active_events(self, session: AsyncSession) -> list[AlertEvent]:
        """Get all currently firing or acknowledged alerts."""
        result = await session.exec(
            select(AlertEvent)
            .where(AlertEvent.status != AlertStatus.RESOLVED)  # type: ignore[arg-type]
            .order_by(AlertEvent.severity, AlertEvent.fired_at.desc())  # type: ignore
        )
        return list(result.all())

    async def _notify(
        self,
        session: AsyncSession,
        event: AlertEvent,
        rule: AlertRule,
    ) -> None:
        """Send notifications through configured channels."""
        try:
            channels: list[dict[str, Any]] = json.loads(rule.channels)
        except json.JSONDecodeError:
            channels = [{"channel": "email", "destination": None}]

        for ch in channels:
            channel_type = ch.get("channel", "email")
            destination = ch.get("destination")
            success = False
            response_status = None
            response_body = None

            try:
                if channel_type == AlertChannel.EMAIL.value:
                    success, response_status, response_body = await self._send_email_notification(
                        event
                    )
                elif channel_type == AlertChannel.WEBHOOK.value:
                    success, response_status, response_body = await self._send_webhook_notification(
                        event, destination
                    )
                elif channel_type == AlertChannel.PAGERDUTY.value:
                    (
                        success,
                        response_status,
                        response_body,
                    ) = await self._send_pagerduty_notification(event, destination)
                elif channel_type == AlertChannel.OPSGENIE.value:
                    (
                        success,
                        response_status,
                        response_body,
                    ) = await self._send_opsgenie_notification(event, destination)
            except Exception:
                logger.exception("Notification failed for channel %s", channel_type)
                success = False
                response_body = "notification_exception"

            assert event.id is not None, "Event ID must not be None when creating notification"
            notification = AlertNotification(
                alert_event_id=event.id,
                channel=AlertChannel(channel_type),
                destination=destination or "default",
                success=success,
                response_status=response_status,
                response_body=response_body,
            )
            session.add(notification)

        await session.commit()

    async def _send_email_notification(
        self, event: AlertEvent
    ) -> tuple[bool, int | None, str | None]:
        """Send alert via email."""
        admin_emails = settings.ALERT_ADMIN_EMAILS
        if not admin_emails:
            return False, None, "no_admin_emails_configured"

        subject = f"[{event.severity.value}] Alert: {event.name}"
        body = (
            f"Severity: {event.severity.value}\n"
            f"Alert: {event.name}\n"
            f"Message: {event.message}\n"
            f"Metric Value: {event.metric_value}\n"
            f"Threshold: {event.threshold}\n"
            f"Time: {event.fired_at.isoformat()}\n"
        )

        try:
            result = await send_email(admin_emails, subject, body)
            success = result.get("sent", False)
            return success, 200 if success else 500, None
        except Exception as exc:
            return False, 500, str(exc)

    async def _send_webhook_notification(
        self,
        event: AlertEvent,
        destination: str | None,
    ) -> tuple[bool, int | None, str | None]:
        """Send alert via generic webhook."""
        url = destination or settings.OTEL_EXPORTER_OTLP_ENDPOINT
        if not url:
            return False, None, "webhook_url_not_configured"

        payload = {
            "alert": event.name,
            "severity": event.severity.value,
            "status": event.status.value,
            "message": event.message,
            "metric_value": event.metric_value,
            "threshold": event.threshold,
            "timestamp": event.fired_at.isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
            return response.is_success, response.status_code, response.text[:500]
        except Exception as exc:
            return False, None, str(exc)[:500]

    async def _send_pagerduty_notification(
        self,
        event: AlertEvent,
        destination: str | None,
    ) -> tuple[bool, int | None, str | None]:
        """Send alert to PagerDuty Events API v2."""
        routing_key = destination
        if not routing_key:
            return False, None, "pagerduty_routing_key_not_configured"

        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "dedup_key": f"ecommerce-agent-{event.name}-{event.rule_id}",
            "payload": {
                "summary": f"[{event.severity.value}] {event.name}: {event.message}",
                "severity": _map_to_pagerduty_severity(event.severity),
                "source": "ecommerce-smart-agent",
                "custom_details": {
                    "metric_value": event.metric_value,
                    "threshold": event.threshold,
                    "rule_id": event.rule_id,
                },
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                )
            return response.is_success, response.status_code, response.text[:500]
        except Exception as exc:
            return False, None, str(exc)[:500]

    async def _send_opsgenie_notification(
        self,
        event: AlertEvent,
        destination: str | None,
    ) -> tuple[bool, int | None, str | None]:
        """Send alert to OpsGenie Alert API."""
        api_key = destination
        if not api_key:
            return False, None, "opsgenie_api_key_not_configured"

        payload = {
            "message": f"[{event.severity.value}] {event.name}: {event.message}",
            "priority": _map_to_opsgenie_priority(event.severity),
            "alias": f"ecommerce-agent-{event.name}-{event.rule_id}",
            "source": "ecommerce-smart-agent",
            "details": {
                "metric_value": event.metric_value,
                "threshold": event.threshold,
                "rule_id": event.rule_id,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.opsgenie.com/v2/alerts",
                    json=payload,
                    headers={"Authorization": f"GenieKey {api_key}"},
                )
            return response.is_success, response.status_code, response.text[:500]
        except Exception as exc:
            return False, None, str(exc)[:500]

    def fire_alert_sync(
        self,
        session: Any,
        rule: AlertRule,
        metric_value: float,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> AlertEvent | None:
        """Fire an alert event synchronously for Celery tasks."""
        cache_key = f"alert:suppressed:{rule.id}:{rule.name}"
        now = datetime.now(UTC)

        suppressed = False
        try:
            import redis

            sync_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            last_fired_raw = sync_redis.get(cache_key)
            if last_fired_raw:
                last_fired_raw = str(last_fired_raw)
                try:
                    last_fired = datetime.fromisoformat(last_fired_raw)
                    if (now - last_fired).total_seconds() < rule.suppress_interval_seconds:
                        suppressed = True
                except ValueError:
                    pass
            if not suppressed:
                sync_redis.setex(cache_key, rule.suppress_interval_seconds, now.isoformat())
        except Exception:
            last_fired = self._suppression_cache.get(cache_key)
            if last_fired and (now - last_fired).total_seconds() < rule.suppress_interval_seconds:
                suppressed = True
            else:
                self._suppression_cache[cache_key] = now

        if suppressed:
            logger.debug("Alert %s suppressed (sync)", rule.name)
            return None

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

        self._notify_sync(session, event, rule)
        logger.warning("Alert fired: [%s] %s - %s", rule.severity.value, rule.name, message)
        return event

    def _notify_sync(
        self,
        session: Any,
        event: AlertEvent,
        rule: AlertRule,
    ) -> None:
        """Send notifications through configured channels (sync version)."""
        try:
            channels: list[dict[str, Any]] = json.loads(rule.channels)
        except json.JSONDecodeError:
            channels = [{"channel": "email", "destination": None}]

        for ch in channels:
            channel_type = ch.get("channel", "email")
            destination = ch.get("destination")
            success = False
            response_status = None
            response_body = None

            try:
                if channel_type == AlertChannel.EMAIL.value:
                    success, response_status, response_body = self._send_email_notification_sync(
                        event
                    )
                elif channel_type == AlertChannel.WEBHOOK.value:
                    success, response_status, response_body = self._send_webhook_notification_sync(
                        event, destination
                    )
                elif channel_type == AlertChannel.PAGERDUTY.value:
                    (
                        success,
                        response_status,
                        response_body,
                    ) = self._send_pagerduty_notification_sync(event, destination)
                elif channel_type == AlertChannel.OPSGENIE.value:
                    (
                        success,
                        response_status,
                        response_body,
                    ) = self._send_opsgenie_notification_sync(event, destination)
            except Exception:
                logger.exception("Notification failed for channel %s (sync)", channel_type)
                success = False
                response_body = "notification_exception"

            assert event.id is not None, "Event ID must not be None when creating notification"
            notification = AlertNotification(
                alert_event_id=event.id,
                channel=AlertChannel(channel_type),
                destination=destination or "default",
                success=success,
                response_status=response_status,
                response_body=response_body,
            )
            session.add(notification)

        session.commit()

    def _send_email_notification_sync(
        self, event: AlertEvent
    ) -> tuple[bool, int | None, str | None]:
        """Send alert via email (sync version)."""
        import smtplib
        from email.mime.text import MIMEText

        admin_emails = settings.ALERT_ADMIN_EMAILS
        if not admin_emails:
            return False, None, "no_admin_emails_configured"

        subject = f"[{event.severity.value}] Alert: {event.name}"
        body = (
            f"Severity: {event.severity.value}\n"
            f"Alert: {event.name}\n"
            f"Message: {event.message}\n"
            f"Metric Value: {event.metric_value}\n"
            f"Threshold: {event.threshold}\n"
            f"Time: {event.fired_at.isoformat()}\n"
        )

        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
            msg["To"] = ", ".join(admin_emails)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_PORT == 587:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value())
                server.sendmail(msg["From"], admin_emails, msg.as_string())
            return True, 200, None
        except Exception as exc:
            return False, 500, str(exc)

    def _send_webhook_notification_sync(
        self,
        event: AlertEvent,
        destination: str | None,
    ) -> tuple[bool, int | None, str | None]:
        """Send alert via generic webhook (sync version)."""
        import urllib.request

        url = destination or settings.OTEL_EXPORTER_OTLP_ENDPOINT
        if not url:
            return False, None, "webhook_url_not_configured"

        payload = {
            "alert": event.name,
            "severity": event.severity.value,
            "status": event.status.value,
            "message": event.message,
            "metric_value": event.metric_value,
            "threshold": event.threshold,
            "timestamp": event.fired_at.isoformat(),
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return True, response.status, None
        except Exception as exc:
            return False, None, str(exc)[:500]

    def _send_pagerduty_notification_sync(
        self,
        event: AlertEvent,
        destination: str | None,
    ) -> tuple[bool, int | None, str | None]:
        """Send alert to PagerDuty Events API v2 (sync version)."""
        import urllib.request

        routing_key = destination
        if not routing_key:
            return False, None, "pagerduty_routing_key_not_configured"

        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "dedup_key": f"ecommerce-agent-{event.name}-{event.rule_id}",
            "payload": {
                "summary": f"[{event.severity.value}] {event.name}: {event.message}",
                "severity": _map_to_pagerduty_severity(event.severity),
                "source": "ecommerce-smart-agent",
                "custom_details": {
                    "metric_value": event.metric_value,
                    "threshold": event.threshold,
                    "rule_id": event.rule_id,
                },
            },
        }

        try:
            req = urllib.request.Request(
                "https://events.pagerduty.com/v2/enqueue",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return True, response.status, None
        except Exception as exc:
            return False, None, str(exc)[:500]

    def _send_opsgenie_notification_sync(
        self,
        event: AlertEvent,
        destination: str | None,
    ) -> tuple[bool, int | None, str | None]:
        """Send alert to OpsGenie Alert API (sync version)."""
        import urllib.request

        api_key = destination
        if not api_key:
            return False, None, "opsgenie_api_key_not_configured"

        payload = {
            "message": f"[{event.severity.value}] {event.name}: {event.message}",
            "priority": _map_to_opsgenie_priority(event.severity),
            "alias": f"ecommerce-agent-{event.name}-{event.rule_id}",
            "source": "ecommerce-smart-agent",
            "details": {
                "metric_value": event.metric_value,
                "threshold": event.threshold,
                "rule_id": event.rule_id,
            },
        }

        try:
            req = urllib.request.Request(
                "https://api.opsgenie.com/v2/alerts",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"GenieKey {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return True, response.status, None
        except Exception as exc:
            return False, None, str(exc)[:500]


def _map_to_pagerduty_severity(severity: AlertSeverity) -> str:
    mapping = {
        AlertSeverity.P0: "critical",
        AlertSeverity.P1: "error",
        AlertSeverity.P2: "warning",
    }
    return mapping.get(severity, "warning")


def _map_to_opsgenie_priority(severity: AlertSeverity) -> str:
    mapping = {
        AlertSeverity.P0: "P1",
        AlertSeverity.P1: "P2",
        AlertSeverity.P2: "P3",
    }
    return mapping.get(severity, "P3")
