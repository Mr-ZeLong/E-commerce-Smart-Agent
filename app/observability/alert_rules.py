"""Alert rule engine for the E-commerce Smart Agent.

Rules evaluate Prometheus metrics and system state, firing alerts through
``AlertManager`` when thresholds are breached.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings
from app.observability.alerting import Alert, AlertManager, AlertSeverity

logger = logging.getLogger(__name__)


class MetricsProvider(Protocol):
    def get_metric(self, name: str, **labels: Any) -> float | None: ...


@dataclass(frozen=True)
class AlertRule:
    name: str
    severity: AlertSeverity
    message_template: str
    evaluate: Callable[[dict[str, Any]], Alert | None]


class PrometheusMetricsProvider:
    def get_metric(self, name: str, **labels: Any) -> float | None:
        from prometheus_client import CollectorRegistry

        registry = CollectorRegistry()
        for collector in registry.collect():
            for sample in collector.samples:
                if sample.name == name and sample.labels == labels:
                    return float(sample.value)
        return None


class StaticMetricsProvider:
    def __init__(self, data: dict[str, float] | None = None) -> None:
        self._data = data or {}

    def get_metric(self, name: str, **labels: Any) -> float | None:
        key = name
        if labels:
            key = f"{name}:{labels}"
        return self._data.get(key, self._data.get(name))

    def set_metric(self, name: str, value: float) -> None:
        self._data[name] = value


class AlertRuleEngine:
    def __init__(
        self,
        alert_manager: AlertManager,
        metrics: MetricsProvider | None = None,
    ) -> None:
        self.alert_manager = alert_manager
        self.metrics = metrics or PrometheusMetricsProvider()
        self._rules: list[AlertRule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        self._rules = [
            AlertRule(
                name="high_latency",
                severity=AlertSeverity.P1,
                message_template="Chat latency {latency_ms:.0f}ms exceeds 2000ms threshold",
                evaluate=self._eval_latency,
            ),
            AlertRule(
                name="high_error_rate",
                severity=AlertSeverity.P0,
                message_template="Error rate {error_rate:.2%} exceeds 1% threshold",
                evaluate=self._eval_error_rate,
            ),
            AlertRule(
                name="high_hallucination_rate",
                severity=AlertSeverity.P1,
                message_template="Hallucination rate {rate:.2%} exceeds 5% threshold",
                evaluate=self._eval_hallucination_rate,
            ),
            AlertRule(
                name="service_unavailable",
                severity=AlertSeverity.P0,
                message_template="Service health check failed: {reason}",
                evaluate=self._eval_service_unavailable,
            ),
            AlertRule(
                name="high_transfer_rate",
                severity=AlertSeverity.P1,
                message_template="Human transfer rate {rate:.2%} exceeds {threshold:.2%} threshold",
                evaluate=self._eval_transfer_rate,
            ),
            AlertRule(
                name="low_confidence",
                severity=AlertSeverity.P2,
                message_template="Confidence score {score:.2f} below {threshold:.2f} threshold",
                evaluate=self._eval_low_confidence,
            ),
        ]

    async def evaluate_all(self, context: dict[str, Any] | None = None) -> list[Alert]:
        ctx = context or {}
        fired: list[Alert] = []
        for rule in self._rules:
            try:
                alert = rule.evaluate(ctx)
                if alert is not None:
                    fired.append(alert)
                    await self.alert_manager.fire(alert)
            except Exception:
                logger.exception("Rule '%s' evaluation failed", rule.name)
        return fired

    def _eval_latency(self, ctx: dict[str, Any]) -> Alert | None:
        latency_ms = ctx.get("latency_ms")
        if latency_ms is None:
            latency_ms = self.metrics.get_metric("chat_latency_seconds_sum")
            if latency_ms is not None:
                latency_ms = latency_ms * 1000
        if latency_ms is not None and latency_ms > 2000:
            return Alert(
                name="high_latency",
                severity=AlertSeverity.P1,
                message=f"Chat latency {latency_ms:.0f}ms exceeds 2000ms threshold",
                metadata={"latency_ms": latency_ms, "threshold_ms": 2000},
            )
        return None

    def _eval_error_rate(self, ctx: dict[str, Any]) -> Alert | None:
        error_rate = ctx.get("error_rate")
        if error_rate is None:
            total = self.metrics.get_metric("chat_requests_total")
            errors = self.metrics.get_metric("chat_errors_total")
            if total and total > 0 and errors is not None:
                error_rate = errors / total
        if error_rate is not None and error_rate > 0.01:
            return Alert(
                name="high_error_rate",
                severity=AlertSeverity.P0,
                message=f"Error rate {error_rate:.2%} exceeds 1% threshold",
                metadata={"error_rate": error_rate, "threshold": 0.01},
            )
        return None

    def _eval_hallucination_rate(self, ctx: dict[str, Any]) -> Alert | None:
        rate = ctx.get("hallucination_rate")
        if rate is None:
            rate = self.metrics.get_metric("hallucination_rate")
        if rate is not None and rate > 0.05:
            return Alert(
                name="high_hallucination_rate",
                severity=AlertSeverity.P1,
                message=f"Hallucination rate {rate:.2%} exceeds 5% threshold",
                metadata={"hallucination_rate": rate, "threshold": 0.05},
            )
        return None

    def _eval_service_unavailable(self, ctx: dict[str, Any]) -> Alert | None:
        healthy = ctx.get("healthy")
        if healthy is False:
            return Alert(
                name="service_unavailable",
                severity=AlertSeverity.P0,
                message=f"Service health check failed: {ctx.get('reason', 'unknown')}",
                metadata={"reason": ctx.get("reason", "unknown")},
            )
        return None

    def _eval_transfer_rate(self, ctx: dict[str, Any]) -> Alert | None:
        rate = ctx.get("transfer_rate")
        threshold = settings.ALERT_TRANSFER_RATE_THRESHOLD
        if rate is not None and rate > threshold:
            return Alert(
                name="high_transfer_rate",
                severity=AlertSeverity.P1,
                message=f"Human transfer rate {rate:.2%} exceeds {threshold:.2%} threshold",
                metadata={"transfer_rate": rate, "threshold": threshold},
            )
        return None

    def _eval_low_confidence(self, ctx: dict[str, Any]) -> Alert | None:
        score = ctx.get("confidence_score")
        threshold = settings.ALERT_CONFIDENCE_THRESHOLD
        if score is not None and score < threshold:
            return Alert(
                name="low_confidence",
                severity=AlertSeverity.P2,
                message=f"Confidence score {score:.2f} below {threshold:.2f} threshold",
                metadata={"confidence_score": score, "threshold": threshold},
            )
        return None
