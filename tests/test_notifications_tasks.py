from unittest.mock import Mock, patch

from app.tasks.notifications import check_quality_alerts


class MockResult:
    def __init__(self, value):
        self._value = value

    def one(self):
        return self._value


class TestCheckQualityAlerts:
    @patch("app.tasks.notifications.sync_session_maker")
    def test_publish_ws_alert_when_csat_low(self, mock_session_maker):
        mock_session = Mock()
        mock_session.exec.side_effect = [
            MockResult(0),
            MockResult(1),
            MockResult(0),
        ]
        mock_session_maker.return_value.__enter__.return_value = mock_session

        result = check_quality_alerts.run()

        assert result["alert_triggered"] is True

    @patch("app.tasks.notifications.sync_session_maker")
    def test_no_publish_when_alert_not_triggered(self, mock_session_maker):
        mock_session = Mock()
        mock_session.exec.side_effect = [
            MockResult(1),
            MockResult(0),
            MockResult(0),
        ]
        mock_session_maker.return_value.__enter__.return_value = mock_session

        result = check_quality_alerts.run()

        assert result["alert_triggered"] is False

    @patch("app.tasks.notifications.sync_session_maker")
    def test_publish_ws_alert_when_complaints_high(self, mock_session_maker):
        mock_session = Mock()
        mock_session.exec.side_effect = [
            MockResult(1),
            MockResult(0),
            MockResult(11),
        ]
        mock_session_maker.return_value.__enter__.return_value = mock_session

        result = check_quality_alerts.run()

        assert result["alert_triggered"] is True
