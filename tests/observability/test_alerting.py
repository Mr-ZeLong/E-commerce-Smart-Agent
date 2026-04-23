from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.observability.alerting import (
    Alert,
    AlertManager,
    AlertSeverity,
    create_default_alert_manager,
)


class TestAlertManager:
    @pytest.mark.asyncio
    async def test_fire_queues_alert(self):
        handler = AsyncMock()
        manager = AlertManager(batch_window_seconds=0.1, max_batch_size=10)
        manager.register_handler("test", handler)

        alert = Alert(name="test_alert", severity=AlertSeverity.P1, message="something wrong")
        await manager.fire(alert)
        await asyncio.sleep(0.15)

        handler.assert_awaited_once()
        assert handler.await_args is not None
        batch = handler.await_args.args[0]
        assert len(batch) == 1
        assert batch[0].name == "test_alert"

    @pytest.mark.asyncio
    async def test_batch_flush_on_max_size(self):
        handler = AsyncMock()
        manager = AlertManager(batch_window_seconds=60.0, max_batch_size=3)
        manager.register_handler("test", handler)

        for i in range(3):
            await manager.fire(Alert(name=f"a{i}", severity=AlertSeverity.P2, message="m"))

        handler.assert_awaited_once()
        assert handler.await_args is not None
        assert len(handler.await_args.args[0]) == 3

    @pytest.mark.asyncio
    async def test_multiple_handlers_receive_same_batch(self):
        h1 = AsyncMock()
        h2 = AsyncMock()
        manager = AlertManager(batch_window_seconds=0.05, max_batch_size=10)
        manager.register_handler("h1", h1)
        manager.register_handler("h2", h2)

        await manager.fire(Alert(name="x", severity=AlertSeverity.P0, message="y"))
        await asyncio.sleep(0.1)

        h1.assert_awaited_once()
        h2.assert_awaited_once()
        assert h1.await_args is not None
        assert h2.await_args is not None
        assert len(h1.await_args.args[0]) == len(h2.await_args.args[0]) == 1

    @pytest.mark.asyncio
    async def test_unregister_handler_removes_it(self):
        handler = AsyncMock()
        manager = AlertManager(batch_window_seconds=0.05, max_batch_size=10)
        manager.register_handler("test", handler)
        manager.unregister_handler("test")

        await manager.fire(Alert(name="x", severity=AlertSeverity.P1, message="y"))
        await asyncio.sleep(0.1)

        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_shutdown_flushes_pending(self):
        handler = AsyncMock()
        manager = AlertManager(batch_window_seconds=60.0, max_batch_size=100)
        manager.register_handler("test", handler)

        await manager.fire(Alert(name="x", severity=AlertSeverity.P1, message="y"))
        await manager.shutdown()

        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handler_failure_does_not_crush_others(self):
        bad = AsyncMock(side_effect=RuntimeError("boom"))
        good = AsyncMock()
        manager = AlertManager(batch_window_seconds=0.05, max_batch_size=10)
        manager.register_handler("bad", bad)
        manager.register_handler("good", good)

        await manager.fire(Alert(name="x", severity=AlertSeverity.P1, message="y"))
        await asyncio.sleep(0.1)

        bad.assert_awaited_once()
        good.assert_awaited_once()


class TestCreateDefaultAlertManager:
    @pytest.mark.asyncio
    async def test_has_email_and_webhook_handlers(self):
        manager = create_default_alert_manager()
        assert "email" in set(manager._handlers)
        assert "webhook" in set(manager._handlers)

    @pytest.mark.asyncio
    async def test_email_handler_skips_when_no_admin_emails(self):
        with (
            patch("app.observability.alerting.settings.ALERT_ADMIN_EMAILS", []),
            patch("app.observability.alerting.send_email", new_callable=AsyncMock) as mock_send,
        ):
            from app.observability.alerting import _send_alert_email_batch

            await _send_alert_email_batch([Alert(name="a", severity=AlertSeverity.P0, message="m")])
            mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_email_handler_sends_when_admin_emails_configured(self):
        with (
            patch("app.observability.alerting.settings.ALERT_ADMIN_EMAILS", ["admin@test.com"]),
            patch("app.observability.alerting.send_email", new_callable=AsyncMock) as mock_send,
        ):
            from app.observability.alerting import _send_alert_email_batch

            await _send_alert_email_batch(
                [
                    Alert(name="a", severity=AlertSeverity.P0, message="m1"),
                    Alert(name="b", severity=AlertSeverity.P1, message="m2"),
                ]
            )
            mock_send.assert_awaited_once()
            assert mock_send.await_args is not None
            subject = mock_send.await_args.args[1]
            assert "P0:1" in subject
            assert "P1:1" in subject
