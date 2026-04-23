"""Alert manager for the E-commerce Smart Agent.

DEPRECATED: Use app.services.alert_service.AlertService instead.
This module is kept for backward compatibility.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.core.config import settings
from app.core.email import send_email

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


@dataclass
class Alert:
    name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


AlertHandler = Callable[[list[Alert]], Awaitable[None]]


class AlertManager:
    def __init__(
        self,
        *,
        batch_window_seconds: float = 60.0,
        max_batch_size: int = 50,
    ) -> None:
        self._handlers: dict[str, AlertHandler] = {}
        self._pending: list[Alert] = []
        self._batch_window = batch_window_seconds
        self._max_batch_size = max_batch_size
        self._batch_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def register_handler(self, name: str, handler: AlertHandler) -> None:
        self._handlers[name] = handler

    def unregister_handler(self, name: str) -> None:
        self._handlers.pop(name, None)

    async def fire(self, alert: Alert) -> None:
        async with self._lock:
            self._pending.append(alert)
            should_flush = len(self._pending) >= self._max_batch_size

        logger.warning(
            "Alert fired: [%s] %s - %s",
            alert.severity.value,
            alert.name,
            alert.message,
        )

        if should_flush:
            await self._flush()
        elif self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self._batch_window)
        await self._flush()

    async def _flush(self) -> None:
        async with self._lock:
            if not self._pending:
                return
            batch = self._pending[:]
            self._pending.clear()

        if not self._handlers:
            logger.warning("No alert handlers registered; dropping %d alerts", len(batch))
            return

        for name, handler in self._handlers.items():
            try:
                await handler(batch)
            except Exception:
                logger.exception("Alert handler '%s' failed", name)

    async def shutdown(self) -> None:
        if self._batch_task is not None and not self._batch_task.done():
            self._batch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._batch_task
        await self._flush()


async def _send_alert_email_batch(alerts: list[Alert]) -> None:
    admin_emails = settings.ALERT_ADMIN_EMAILS
    if not admin_emails:
        logger.warning("ALERT_ADMIN_EMAILS empty; skipping email alerts")
        return

    p0_count = sum(1 for a in alerts if a.severity == AlertSeverity.P0)
    p1_count = sum(1 for a in alerts if a.severity == AlertSeverity.P1)
    p2_count = sum(1 for a in alerts if a.severity == AlertSeverity.P2)

    subject = (
        f"[E-commerce Smart Agent] {len(alerts)} alerts (P0:{p0_count} P1:{p1_count} P2:{p2_count})"
    )

    def _alert_lines(alert: Alert) -> list[str]:
        return [
            f"Severity: {alert.severity.value}",
            f"Alert: {alert.name}",
            f"Time: {alert.timestamp.isoformat()}",
            f"Message: {alert.message}",
            f"Details: {json.dumps(alert.metadata, ensure_ascii=False, default=str)}",
            "-" * 40,
        ]

    body = "\n\n".join("\n".join(_alert_lines(a)) for a in alerts)

    await send_email(admin_emails, subject, body)


async def _webhook_handler_stub(alerts: list[Alert]) -> None:
    _ = alerts
    logger.info("Webhook handler called (not configured)")


def create_default_alert_manager() -> AlertManager:
    manager = AlertManager()
    manager.register_handler("email", _send_alert_email_batch)
    manager.register_handler("webhook", _webhook_handler_stub)
    return manager
