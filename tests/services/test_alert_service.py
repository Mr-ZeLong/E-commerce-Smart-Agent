"""Smoke tests for AlertService.

Covers the core alert lifecycle: firing, suppression, and fallback behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.alert import AlertRule, AlertRuleStatus, AlertSeverity, AlertStatus
from app.services.alert_service import AlertService


@pytest.fixture
def alert_service() -> AlertService:
    return AlertService(redis=None)


@pytest.fixture
def sample_rule() -> AlertRule:
    return AlertRule(
        id=1,
        name="test_rule",
        metric="latency",
        operator="gt",
        threshold=100.0,
        duration_seconds=60,
        severity=AlertSeverity.P1,
        status=AlertRuleStatus.ENABLED,
        channels="[]",
        suppress_interval_seconds=300,
        auto_resolve=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestFireAlert:
    @pytest.mark.asyncio
    async def test_creates_event_when_not_suppressed(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        event = await alert_service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=150.0,
            message="latency is high",
        )

        assert event is not None
        assert event.rule_id == sample_rule.id
        assert event.name == sample_rule.name
        assert event.severity == sample_rule.severity
        assert event.status == AlertStatus.FIRING
        assert event.metric_value == 150.0
        mock_session.add.assert_called_once()
        assert mock_session.commit.await_count >= 1

    @pytest.mark.asyncio
    async def test_suppresses_within_interval(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # First alert should fire.
        first = await alert_service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=150.0,
            message="first",
        )
        assert first is not None

        # Second alert within suppression window should be suppressed.
        second = await alert_service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=200.0,
            message="second",
        )
        assert second is None

    @pytest.mark.asyncio
    async def test_allows_after_suppression_window(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
        # Reduce suppression interval for faster test.
        sample_rule.suppress_interval_seconds = 0

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        first = await alert_service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=150.0,
            message="first",
        )
        assert first is not None

        second = await alert_service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=200.0,
            message="second",
        )
        assert second is not None


class TestRedisSuppression:
    @pytest.mark.asyncio
    async def test_redis_suppresses_duplicate(self, sample_rule: AlertRule):
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=datetime.now(UTC).isoformat())
        redis_mock.setex = AsyncMock()

        service = AlertService(redis=redis_mock)
        mock_session = AsyncMock(spec=AsyncSession)

        event = await service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=150.0,
            message="test",
        )

        assert event is None
        redis_mock.get.assert_awaited_once_with("alert:suppressed:1:test_rule")
        redis_mock.setex.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_write_failure_falls_back_to_memory(self, sample_rule: AlertRule):
        import redis.asyncio as aioredis

        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.setex = AsyncMock(side_effect=aioredis.RedisError("connection lost"))

        service = AlertService(redis=redis_mock)
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        event = await service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=150.0,
            message="test",
        )

        assert event is not None
        # Subsequent alert should be suppressed via memory fallback.
        second = await service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=200.0,
            message="second",
        )
        assert second is None
