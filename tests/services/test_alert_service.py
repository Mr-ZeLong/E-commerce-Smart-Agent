"""Smoke tests for AlertService.

Covers the core alert lifecycle: firing, suppression, and fallback behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.alert import AlertEvent, AlertRule, AlertRuleStatus, AlertSeverity, AlertStatus
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
    async def test_returns_none_when_suppressed(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
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

        # Second alert within suppression window should be suppressed.
        second = await alert_service.fire_alert(
            session=mock_session,
            rule=sample_rule,
            metric_value=200.0,
            message="second",
        )
        assert second is None


class _MockRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def setex(self, key: str, seconds: int, value: str) -> None:
        self.data[key] = value


class TestFireAlertSync:
    def test_creates_event_when_not_suppressed(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
        mock_session = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value = _MockRedis()
            event = alert_service.fire_alert_sync(
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
        assert mock_session.commit.call_count >= 1

    def test_returns_none_when_suppressed(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
        mock_session = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value = _MockRedis()
            first = alert_service.fire_alert_sync(
                session=mock_session,
                rule=sample_rule,
                metric_value=150.0,
                message="first",
            )
            assert first is not None

            mock_session.reset_mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            second = alert_service.fire_alert_sync(
                session=mock_session,
                rule=sample_rule,
                metric_value=200.0,
                message="second",
            )
            assert second is None

    def test_uses_in_memory_suppression_cache(
        self,
        alert_service: AlertService,
        sample_rule: AlertRule,
    ):
        sample_rule.suppress_interval_seconds = 0

        mock_session = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        with patch("redis.from_url") as mock_from_url:
            mock_from_url.return_value = _MockRedis()
            first = alert_service.fire_alert_sync(
                session=mock_session,
                rule=sample_rule,
                metric_value=150.0,
                message="first",
            )
            assert first is not None

            second = alert_service.fire_alert_sync(
                session=mock_session,
                rule=sample_rule,
                metric_value=200.0,
                message="second",
            )
            assert second is not None


class TestNotifySync:
    def test_notify_sync_logs_notification_records(
        self, alert_service: AlertService, sample_rule: AlertRule
    ):
        mock_session = Mock()
        mock_session.commit = Mock()
        mock_session.add = Mock()

        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )
        event.id = 1

        sample_rule.channels = '[{"channel": "email"}]'

        with patch.object(
            alert_service, "_send_email_notification_sync", return_value=(True, 200, None)
        ):
            alert_service._notify_sync(mock_session, event, sample_rule)

        mock_session.add.assert_called()
        mock_session.commit.assert_called_once()


class TestSendEmailNotificationSync:
    def test_returns_no_admin_emails_when_not_configured(
        self, alert_service: AlertService, sample_rule: AlertRule
    ):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        with patch("app.services.alert_service.settings") as mock_settings:
            mock_settings.ALERT_ADMIN_EMAILS = []
            mock_settings.SMTP_HOST = "localhost"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user"
            mock_settings.SMTP_PASSWORD.get_secret_value.return_value = "pass"
            mock_settings.SMTP_FROM_EMAIL = None

            success, status_code, body = alert_service._send_email_notification_sync(event)

        assert success is False
        assert status_code is None
        assert body == "no_admin_emails_configured"

    def test_sends_email_via_smtplib(self, alert_service: AlertService, sample_rule: AlertRule):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        with patch("app.services.alert_service.settings") as mock_settings:
            mock_settings.ALERT_ADMIN_EMAILS = ["admin@example.com"]
            mock_settings.SMTP_HOST = "localhost"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user"
            mock_settings.SMTP_PASSWORD.get_secret_value.return_value = "pass"
            mock_settings.SMTP_FROM_EMAIL = None

            with patch("smtplib.SMTP") as mock_smtp:
                mock_smtp.return_value.__enter__ = Mock(return_value=mock_smtp.return_value)
                mock_smtp.return_value.__exit__ = Mock(return_value=False)
                mock_smtp.return_value.starttls = Mock()
                mock_smtp.return_value.login = Mock()
                mock_smtp.return_value.sendmail = Mock()

                success, status_code, body = alert_service._send_email_notification_sync(event)

        assert success is True
        assert status_code == 200
        assert body is None


class TestSendWebhookNotificationSync:
    def test_returns_webhook_url_not_configured(
        self, alert_service: AlertService, sample_rule: AlertRule
    ):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        with patch("app.services.alert_service.settings") as mock_settings:
            mock_settings.OTEL_EXPORTER_OTLP_ENDPOINT = ""

            success, status_code, body = alert_service._send_webhook_notification_sync(event, None)

        assert success is False
        assert status_code is None
        assert body == "webhook_url_not_configured"

    def test_sends_webhook_via_urllib(self, alert_service: AlertService, sample_rule: AlertRule):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            success, status_code, body = alert_service._send_webhook_notification_sync(
                event, "https://example.com/webhook"
            )

        assert success is True
        assert status_code == 200
        assert body is None


class TestSendPagerdutyNotificationSync:
    def test_returns_pagerduty_routing_key_not_configured(
        self, alert_service: AlertService, sample_rule: AlertRule
    ):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        success, status_code, body = alert_service._send_pagerduty_notification_sync(event, None)

        assert success is False
        assert status_code is None
        assert body == "pagerduty_routing_key_not_configured"

    def test_sends_pagerduty_via_urllib(self, alert_service: AlertService, sample_rule: AlertRule):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.status = 202
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            success, status_code, body = alert_service._send_pagerduty_notification_sync(
                event, "test_routing_key"
            )

        assert success is True
        assert status_code == 202
        assert body is None


class TestSendOpsgenieNotificationSync:
    def test_returns_opsgenie_api_key_not_configured(
        self, alert_service: AlertService, sample_rule: AlertRule
    ):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        success, status_code, body = alert_service._send_opsgenie_notification_sync(event, None)

        assert success is False
        assert status_code is None
        assert body == "opsgenie_api_key_not_configured"

    def test_sends_opsgenie_via_urllib(self, alert_service: AlertService, sample_rule: AlertRule):
        event = AlertEvent(
            rule_id=sample_rule.id,
            name=sample_rule.name,
            severity=sample_rule.severity,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=150.0,
            threshold=100.0,
            metadata_json="{}",
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.status = 201
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            success, status_code, body = alert_service._send_opsgenie_notification_sync(
                event, "test_api_key"
            )

        assert success is True
        assert status_code == 201
        assert body is None


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
