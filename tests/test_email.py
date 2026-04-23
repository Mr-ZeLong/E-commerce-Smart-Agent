from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from app.core.email import send_email


@pytest.mark.asyncio
async def test_send_email_skips_when_smtp_not_configured():
    with patch("app.core.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = ""
        mock_settings.SMTP_USER = ""
        result = await send_email(["user@test.com"], "subject", "body")
        assert result == {"sent": False, "reason": "smtp_not_configured"}


@pytest.mark.asyncio
async def test_send_email_success_with_starttls():
    mock_server = MagicMock()
    with patch("app.core.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@test.com"
        mock_settings.SMTP_PASSWORD = SecretStr("pass")
        mock_settings.SMTP_FROM_EMAIL = "noreply@test.com"
        with patch("app.core.email.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = await send_email(["to@test.com"], "Test Subject", "Test Body")
            assert result["sent"] is True
            assert result["recipients"] == ["to@test.com"]
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@test.com", "pass")
            mock_server.sendmail.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_success_without_starttls():
    mock_server = MagicMock()
    with patch("app.core.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 465
        mock_settings.SMTP_USER = "user@test.com"
        mock_settings.SMTP_PASSWORD = SecretStr("pass")
        mock_settings.SMTP_FROM_EMAIL = None
        with patch("app.core.email.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = await send_email(["to@test.com"], "Test Subject", "Test Body")
            assert result["sent"] is True
            mock_server.starttls.assert_not_called()
            mock_server.login.assert_called_once_with("user@test.com", "pass")


@pytest.mark.asyncio
async def test_send_email_returns_error_on_exception():
    mock_server = MagicMock()
    mock_server.sendmail.side_effect = Exception("SMTP error")
    with patch("app.core.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@test.com"
        mock_settings.SMTP_PASSWORD = SecretStr("pass")
        mock_settings.SMTP_FROM_EMAIL = "noreply@test.com"
        with patch("app.core.email.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = await send_email(["to@test.com"], "Test Subject", "Test Body")
            assert result == {"sent": False, "reason": "smtp_error"}
