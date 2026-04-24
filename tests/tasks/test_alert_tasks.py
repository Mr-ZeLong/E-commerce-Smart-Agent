"""Tests for alert evaluation Celery tasks.

Verifies that alert rules are evaluated correctly, suppression counters
work, and service health checks fire alerts when appropriate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.models.alert import AlertEvent, AlertRule, AlertRuleStatus, AlertSeverity, AlertStatus
from app.tasks.alert_tasks import (
    _auto_resolve_cleared_alerts,
    _evaluate_operator,
    _get_metric_value,
    check_service_health,
    evaluate_alert_rules,
)


@pytest.fixture
def sample_rule():
    return AlertRule(
        id=1,
        name="high_latency",
        metric="avg_latency_ms",
        operator="gt",
        threshold=1000.0,
        duration_seconds=120,
        severity=AlertSeverity.P1,
        status=AlertRuleStatus.ENABLED,
        channels='[{"channel": "email"}]',
        suppress_interval_seconds=300,
        auto_resolve=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestEvaluateOperator:
    def test_gt(self):
        assert _evaluate_operator(150.0, "gt", 100.0) is True
        assert _evaluate_operator(100.0, "gt", 100.0) is False

    def test_gte(self):
        assert _evaluate_operator(100.0, "gte", 100.0) is True
        assert _evaluate_operator(99.0, "gte", 100.0) is False

    def test_lt(self):
        assert _evaluate_operator(50.0, "lt", 100.0) is True
        assert _evaluate_operator(100.0, "lt", 100.0) is False

    def test_lte(self):
        assert _evaluate_operator(100.0, "lte", 100.0) is True
        assert _evaluate_operator(101.0, "lte", 100.0) is False

    def test_eq(self):
        assert _evaluate_operator(100.0, "eq", 100.0) is True
        assert _evaluate_operator(99.0, "eq", 100.0) is False

    def test_ne(self):
        assert _evaluate_operator(99.0, "ne", 100.0) is True
        assert _evaluate_operator(100.0, "ne", 100.0) is False

    def test_unknown_operator(self):
        assert _evaluate_operator(100.0, "unknown", 100.0) is False


class TestGetMetricValue:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        self.engine = engine
        yield
        engine.dispose()

    def test_avg_latency_ms(self):
        with Session(self.engine) as session:
            val, meta = _get_metric_value("avg_latency_ms", 3600)
            assert val is None or val == 0.0
            assert "window_seconds" in meta

    def test_error_rate_no_data(self):
        with Session(self.engine) as session:
            val, meta = _get_metric_value("error_rate", 3600)
            assert val is None
            assert "window_seconds" in meta

    def test_transfer_rate_no_data(self):
        with Session(self.engine) as session:
            val, meta = _get_metric_value("transfer_rate", 3600)
            assert val is None
            assert "window_seconds" in meta

    def test_hallucination_rate_no_data(self):
        with Session(self.engine) as session:
            val, meta = _get_metric_value("hallucination_rate", 3600)
            assert val is None
            assert "window_seconds" in meta

    def test_health_status(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            with Session(self.engine) as session:
                val, meta = _get_metric_value("health_status", 30)
                assert val == 1.0
                assert "window_seconds" in meta

    def test_health_status_failure(self):
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with Session(self.engine) as session:
                val, meta = _get_metric_value("health_status", 30)
                assert val == 0.0
                assert "window_seconds" in meta

    def test_unknown_metric(self):
        with Session(self.engine) as session:
            val, meta = _get_metric_value("unknown_metric", 3600)
            assert val is None
            assert "window_seconds" in meta


def _make_mock_session(rules=None, events=None):
    """Create a mock session that handles both rule queries and event queries."""
    mock_session = MagicMock()
    mock_session.__enter__ = Mock(return_value=mock_session)
    mock_session.__exit__ = Mock(return_value=False)

    def exec_side_effect(stmt):
        mock_result = MagicMock()
        # Check if this is an AlertRule query or AlertEvent query
        stmt_str = str(stmt)
        if "alert_rules" in stmt_str:
            mock_result.all.return_value = rules or []
            mock_result.first.return_value = (rules or [None])[0] if rules else None
        elif "alert_events" in stmt_str:
            mock_result.all.return_value = events or []
        else:
            mock_result.all.return_value = []
            mock_result.first.return_value = None
        return mock_result

    mock_session.exec.side_effect = exec_side_effect
    return mock_session


class TestEvaluateAlertRules:
    def test_no_rules_returns_zero_counts(self):
        mock_session = _make_mock_session(rules=[])

        with patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            result = evaluate_alert_rules()

        assert result["rules_checked"] == 0
        assert result["alerts_fired"] == 0
        assert result["alerts_suppressed"] == 0

    def test_breached_rule_fires_alert(self, sample_rule):
        mock_session = _make_mock_session(rules=[sample_rule], events=[])

        mock_event = MagicMock()
        mock_event.id = 1

        with patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch(
                "app.tasks.alert_tasks._get_metric_value", return_value=(1500.0, {"test": True})
            ):
                with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service.fire_alert_sync.return_value = mock_event
                    mock_service_class.return_value = mock_service

                    result = evaluate_alert_rules()

        assert result["rules_checked"] == 1
        assert result["alerts_fired"] == 1
        assert result["alerts_suppressed"] == 0
        mock_service.fire_alert_sync.assert_called_once()

    def test_not_breached_rule_skips_alert(self, sample_rule):
        mock_session = _make_mock_session(rules=[sample_rule], events=[])

        with patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch(
                "app.tasks.alert_tasks._get_metric_value", return_value=(500.0, {"test": True})
            ):
                with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    result = evaluate_alert_rules()

        assert result["rules_checked"] == 1
        assert result["alerts_fired"] == 0
        assert result["alerts_suppressed"] == 0
        mock_service.fire_alert_sync.assert_not_called()

    def test_suppressed_alert_increments_counter(self, sample_rule):
        mock_session = _make_mock_session(rules=[sample_rule], events=[])

        with patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch(
                "app.tasks.alert_tasks._get_metric_value", return_value=(1500.0, {"test": True})
            ):
                with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service.fire_alert_sync.return_value = None
                    mock_service_class.return_value = mock_service

                    result = evaluate_alert_rules()

        assert result["rules_checked"] == 1
        assert result["alerts_fired"] == 0
        assert result["alerts_suppressed"] == 1

    def test_none_metric_value_skips_rule(self, sample_rule):
        mock_session = _make_mock_session(rules=[sample_rule], events=[])

        with patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch("app.tasks.alert_tasks._get_metric_value", return_value=(None, {})):
                with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    result = evaluate_alert_rules()

        assert result["rules_checked"] == 1
        assert result["alerts_fired"] == 0
        mock_service.fire_alert_sync.assert_not_called()

    def test_multiple_rules_evaluated(self):
        rule1 = AlertRule(
            id=1,
            name="high_latency",
            metric="avg_latency_ms",
            operator="gt",
            threshold=1000.0,
            duration_seconds=120,
            severity=AlertSeverity.P1,
            status=AlertRuleStatus.ENABLED,
            channels='[{"channel": "email"}]',
            suppress_interval_seconds=300,
            auto_resolve=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        rule2 = AlertRule(
            id=2,
            name="low_confidence",
            metric="confidence_score",
            operator="lt",
            threshold=0.6,
            duration_seconds=300,
            severity=AlertSeverity.P1,
            status=AlertRuleStatus.ENABLED,
            channels='[{"channel": "email"}]',
            suppress_interval_seconds=300,
            auto_resolve=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_session = _make_mock_session(rules=[rule1, rule2], events=[])

        mock_event = MagicMock()
        mock_event.id = 1

        def mock_get_metric(metric, window):
            if metric == "avg_latency_ms":
                return 1500.0, {}
            elif metric == "confidence_score":
                return 0.5, {}
            return None, {}

        with patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch("app.tasks.alert_tasks._get_metric_value", side_effect=mock_get_metric):
                with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service.fire_alert_sync.return_value = mock_event
                    mock_service_class.return_value = mock_service

                    result = evaluate_alert_rules()

        assert result["rules_checked"] == 2
        assert result["alerts_fired"] == 2
        assert result["alerts_suppressed"] == 0
        assert mock_service.fire_alert_sync.call_count == 2


class TestAutoResolveClearedAlerts:
    def test_resolves_cleared_alerts(self):
        mock_session = MagicMock()

        rule = AlertRule(
            id=1,
            name="test_rule",
            metric="avg_latency_ms",
            operator="gt",
            threshold=1000.0,
            duration_seconds=120,
            severity=AlertSeverity.P1,
            status=AlertRuleStatus.ENABLED,
            auto_resolve=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        event = AlertEvent(
            id=1,
            rule_id=1,
            name="test_rule",
            severity=AlertSeverity.P1,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=1500.0,
            threshold=1000.0,
            metadata_json="{}",
            fired_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [event]
        mock_session.exec.return_value = mock_result
        mock_session.get.return_value = rule

        with patch("app.tasks.alert_tasks._get_metric_value", return_value=(500.0, {})):
            _auto_resolve_cleared_alerts(mock_session)

        assert event.status == AlertStatus.RESOLVED
        assert event.resolved_at is not None
        assert event.resolution_reason == "auto-resolved: condition cleared"
        mock_session.add.assert_called_with(event)
        mock_session.commit.assert_called_once()

    def test_does_not_resolve_if_still_breached(self):
        mock_session = MagicMock()

        rule = AlertRule(
            id=1,
            name="test_rule",
            metric="avg_latency_ms",
            operator="gt",
            threshold=1000.0,
            duration_seconds=120,
            severity=AlertSeverity.P1,
            status=AlertRuleStatus.ENABLED,
            auto_resolve=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        event = AlertEvent(
            id=1,
            rule_id=1,
            name="test_rule",
            severity=AlertSeverity.P1,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=1500.0,
            threshold=1000.0,
            metadata_json="{}",
            fired_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [event]
        mock_session.exec.return_value = mock_result
        mock_session.get.return_value = rule

        with patch("app.tasks.alert_tasks._get_metric_value", return_value=(1500.0, {})):
            _auto_resolve_cleared_alerts(mock_session)

        assert event.status == AlertStatus.FIRING
        # _auto_resolve_cleared_alerts always calls commit at the end
        mock_session.commit.assert_called_once()

    def test_skips_if_no_rule_id(self):
        mock_session = MagicMock()

        event = AlertEvent(
            id=1,
            rule_id=None,
            name="test_rule",
            severity=AlertSeverity.P1,
            status=AlertStatus.FIRING,
            message="test",
            metric_value=1500.0,
            threshold=1000.0,
            metadata_json="{}",
            fired_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [event]
        mock_session.exec.return_value = mock_result

        _auto_resolve_cleared_alerts(mock_session)

        assert event.status == AlertStatus.FIRING
        mock_session.get.assert_not_called()
        # _auto_resolve_cleared_alerts always calls commit at the end
        mock_session.commit.assert_called_once()


class TestCheckServiceHealth:
    def test_healthy_service(self):
        with patch("app.tasks.alert_tasks._get_metric_value", return_value=(1.0, {"status": 200})):
            result = check_service_health()

        assert result["healthy"] is True
        assert "metadata" in result

    def test_unhealthy_service_fires_alert(self):
        mock_rule = AlertRule(
            id=1,
            name="service_unavailable",
            metric="health_status",
            operator="eq",
            threshold=0.0,
            duration_seconds=60,
            severity=AlertSeverity.P0,
            status=AlertRuleStatus.ENABLED,
            channels='[{"channel": "email"}]',
            suppress_interval_seconds=60,
            auto_resolve=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_session = _make_mock_session(rules=[mock_rule])

        with patch(
            "app.tasks.alert_tasks._get_metric_value", return_value=(0.0, {"error": "timeout"})
        ), patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                mock_service = MagicMock()
                mock_service_class.return_value = mock_service

                result = check_service_health()

        assert result["healthy"] is False
        mock_service.fire_alert_sync.assert_called_once()

    def test_unhealthy_no_rule_configured(self):
        mock_session = _make_mock_session(rules=[])

        with patch(
            "app.tasks.alert_tasks._get_metric_value", return_value=(0.0, {"error": "timeout"})
        ), patch("app.tasks.alert_tasks.sync_session_maker", return_value=mock_session):
            with patch("app.tasks.alert_tasks.AlertService") as mock_service_class:
                mock_service = MagicMock()
                mock_service_class.return_value = mock_service

                result = check_service_health()

        assert result["healthy"] is False
        mock_service.fire_alert_sync.assert_not_called()

    def test_none_value_returns_failed(self):
        with patch("app.tasks.alert_tasks._get_metric_value", return_value=(None, {})):
            result = check_service_health()

        assert result["healthy"] is False
        assert result["reason"] == "health_check_failed"
