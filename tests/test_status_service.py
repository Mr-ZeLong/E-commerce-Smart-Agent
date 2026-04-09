from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.audit import AuditAction
from app.schemas.status import StatusResponse
from app.services.status_service import StatusService


class TestGetThreadStatus:
    @pytest.mark.asyncio
    async def test_pending_returns_waiting_admin(self):
        mock_audit = MagicMock()
        mock_audit.action = AuditAction.PENDING
        mock_audit.id = 1
        mock_audit.risk_level = "HIGH"
        mock_audit.trigger_reason = "risk"
        mock_audit.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=mock_audit)),
                MagicMock(first=MagicMock(return_value=None)),
            ]
        )

        service = StatusService()
        result = await service.get_thread_status(mock_session, 42, "thread-abc")

        assert isinstance(result, StatusResponse)
        assert result.status == "WAITING_ADMIN"
        assert result.thread_id == "42__thread-abc"
        assert result.data["audit_log_id"] == 1
        assert result.data["risk_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_approve_returns_approved(self):
        mock_audit = MagicMock()
        mock_audit.action = AuditAction.APPROVE
        mock_audit.admin_comment = "ok"
        mock_audit.reviewed_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)
        mock_audit.updated_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=mock_audit)),
                MagicMock(first=MagicMock(return_value=None)),
            ]
        )

        service = StatusService()
        result = await service.get_thread_status(mock_session, 42, "thread-abc")

        assert isinstance(result, StatusResponse)
        assert result.status == "APPROVED"
        assert result.data["admin_comment"] == "ok"

    @pytest.mark.asyncio
    async def test_reject_returns_rejected(self):
        mock_audit = MagicMock()
        mock_audit.action = AuditAction.REJECT
        mock_audit.admin_comment = "invalid"
        mock_audit.reviewed_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)
        mock_audit.updated_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=mock_audit)),
                MagicMock(first=MagicMock(return_value=None)),
            ]
        )

        service = StatusService()
        result = await service.get_thread_status(mock_session, 42, "thread-abc")

        assert isinstance(result, StatusResponse)
        assert result.status == "REJECTED"
        assert "invalid" in result.message

    @pytest.mark.asyncio
    async def test_no_audit_log_returns_processing(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=None)),
                MagicMock(first=MagicMock(return_value=mock_message)),
            ]
        )

        service = StatusService()
        result = await service.get_thread_status(mock_session, 42, "thread-abc")

        assert isinstance(result, StatusResponse)
        assert result.status == "PROCESSING"
        assert result.timestamp == "2024-01-01T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_no_audit_log_and_no_message_returns_processing_with_empty_timestamp(self):
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=None)),
                MagicMock(first=MagicMock(return_value=None)),
            ]
        )

        service = StatusService()
        result = await service.get_thread_status(mock_session, 42, "thread-abc")

        assert isinstance(result, StatusResponse)
        assert result.status == "PROCESSING"
        assert result.timestamp == ""
