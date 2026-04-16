from unittest.mock import AsyncMock, patch

from app.tasks.notifications import check_quality_alerts
from app.websocket.redis_bridge import RedisBroadcastBridge


class MockResult:
    def __init__(self, value):
        self._value = value

    def one(self):
        return self._value


class TestCheckQualityAlerts:
    @patch.object(RedisBroadcastBridge, "publish", new_callable=AsyncMock)
    @patch("app.tasks.notifications.async_session_maker")
    def test_publish_ws_alert_when_csat_low(self, mock_session_maker, mock_publish):
        mock_session = AsyncMock()
        mock_session.exec.side_effect = [
            MockResult(0),
            MockResult(1),
            MockResult(0),
        ]
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = check_quality_alerts.run()

        assert result["alert_triggered"] is True
        mock_publish.assert_awaited_once()
        call_kwargs = mock_publish.await_args.kwargs
        assert call_kwargs["event"] == "notification"
        assert call_kwargs["room"] == "admins"
        assert call_kwargs["data"]["type"] == "notification"
        assert call_kwargs["data"]["title"] == "智能客服质量告警"
        assert call_kwargs["data"]["severity"] == "warning"

    @patch.object(RedisBroadcastBridge, "publish", new_callable=AsyncMock)
    @patch("app.tasks.notifications.async_session_maker")
    def test_no_publish_when_alert_not_triggered(self, mock_session_maker, mock_publish):
        mock_session = AsyncMock()
        mock_session.exec.side_effect = [
            MockResult(1),
            MockResult(0),
            MockResult(0),
        ]
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = check_quality_alerts.run()

        assert result["alert_triggered"] is False
        mock_publish.assert_not_awaited()

    @patch.object(RedisBroadcastBridge, "publish", new_callable=AsyncMock)
    @patch("app.tasks.notifications.async_session_maker")
    def test_publish_ws_alert_when_complaints_high(self, mock_session_maker, mock_publish):
        mock_session = AsyncMock()
        mock_session.exec.side_effect = [
            MockResult(1),
            MockResult(0),
            MockResult(11),
        ]
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = check_quality_alerts.run()

        assert result["alert_triggered"] is True
        mock_publish.assert_awaited_once()
