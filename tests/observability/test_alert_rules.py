from __future__ import annotations

import pytest

from app.observability.alert_rules import AlertRuleEngine, StaticMetricsProvider
from app.observability.alerting import AlertManager, AlertSeverity


class TestAlertRuleEngine:
    @pytest.fixture
    def engine(self):
        manager = AlertManager(batch_window_seconds=60.0, max_batch_size=100)
        metrics = StaticMetricsProvider()
        return AlertRuleEngine(manager, metrics=metrics)

    @pytest.mark.asyncio
    async def test_high_latency_fires_when_over_threshold(self, engine):
        fired = await engine.evaluate_all(context={"latency_ms": 3000})
        assert len(fired) == 1
        assert fired[0].name == "high_latency"
        assert fired[0].severity == AlertSeverity.P1

    @pytest.mark.asyncio
    async def test_high_latency_does_not_fire_when_under_threshold(self, engine):
        fired = await engine.evaluate_all(context={"latency_ms": 500})
        assert len(fired) == 0

    @pytest.mark.asyncio
    async def test_error_rate_fires_when_over_threshold(self, engine):
        fired = await engine.evaluate_all(context={"error_rate": 0.02})
        assert len(fired) == 1
        assert fired[0].name == "high_error_rate"
        assert fired[0].severity == AlertSeverity.P0

    @pytest.mark.asyncio
    async def test_error_rate_does_not_fire_when_under_threshold(self, engine):
        fired = await engine.evaluate_all(context={"error_rate": 0.005})
        assert len(fired) == 0

    @pytest.mark.asyncio
    async def test_hallucination_rate_fires_when_over_threshold(self, engine):
        fired = await engine.evaluate_all(context={"hallucination_rate": 0.06})
        assert len(fired) == 1
        assert fired[0].name == "high_hallucination_rate"
        assert fired[0].severity == AlertSeverity.P1

    @pytest.mark.asyncio
    async def test_service_unavailable_fires_when_healthy_false(self, engine):
        fired = await engine.evaluate_all(context={"healthy": False, "reason": "db_down"})
        assert len(fired) == 1
        assert fired[0].name == "service_unavailable"
        assert fired[0].severity == AlertSeverity.P0

    @pytest.mark.asyncio
    async def test_service_unavailable_does_not_fire_when_healthy_true(self, engine):
        fired = await engine.evaluate_all(context={"healthy": True})
        assert len(fired) == 0

    @pytest.mark.asyncio
    async def test_transfer_rate_fires_when_over_threshold(self, engine):
        fired = await engine.evaluate_all(context={"transfer_rate": 0.5})
        assert len(fired) == 1
        assert fired[0].name == "high_transfer_rate"
        assert fired[0].severity == AlertSeverity.P1

    @pytest.mark.asyncio
    async def test_low_confidence_fires_when_below_threshold(self, engine):
        fired = await engine.evaluate_all(context={"confidence_score": 0.5})
        assert len(fired) == 1
        assert fired[0].name == "low_confidence"
        assert fired[0].severity == AlertSeverity.P2

    @pytest.mark.asyncio
    async def test_multiple_rules_can_fire(self, engine):
        fired = await engine.evaluate_all(
            context={
                "latency_ms": 3000,
                "error_rate": 0.02,
                "hallucination_rate": 0.06,
                "healthy": False,
                "transfer_rate": 0.5,
                "confidence_score": 0.5,
            }
        )
        names = {a.name for a in fired}
        assert names == {
            "high_latency",
            "high_error_rate",
            "high_hallucination_rate",
            "service_unavailable",
            "high_transfer_rate",
            "low_confidence",
        }

    @pytest.mark.asyncio
    async def test_metrics_provider_fallback(self, engine):
        engine.metrics.set_metric("chat_latency_seconds_sum", 3.0)
        fired = await engine.evaluate_all(context={})
        names = [a.name for a in fired]
        assert "high_latency" in names

    @pytest.mark.asyncio
    async def test_no_fire_when_context_empty_and_metrics_empty(self, engine):
        fired = await engine.evaluate_all(context={})
        assert len(fired) == 0
