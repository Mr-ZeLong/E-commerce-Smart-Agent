from datetime import UTC, datetime

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.utils import build_thread_id
from app.models.audit import AuditAction, AuditLog, AuditTriggerType, RiskLevel
from app.models.message import MessageCard, MessageStatus, MessageType
from app.models.user import User
from app.schemas.status import StatusResponse
from app.services.status_service import StatusService

THREAD_ID = "thread-abc"


def _make_user():
    return User(
        username=f"status_test_{__import__('uuid').uuid4().hex[:8]}",
        email=f"status_{__import__('uuid').uuid4().hex[:8]}@test.com",
        full_name="Status Test User",
        password_hash="fakehash",
    )


class TestGetThreadStatus:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_pending_returns_waiting_admin(self, db_session: AsyncSession):
        user = _make_user()
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        scoped_thread_id = build_thread_id(user.id, THREAD_ID)

        audit = AuditLog(
            user_id=user.id,
            thread_id=scoped_thread_id,
            action=AuditAction.PENDING,
            trigger_type=AuditTriggerType.RISK,
            risk_level=RiskLevel.HIGH,
            trigger_reason="risk",
            context_snapshot={},
            refund_application_id=1,
            order_id=1,
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        db_session.add(audit)
        await db_session.commit()
        await db_session.refresh(audit)

        service = StatusService()
        result = await service.get_thread_status(db_session, user.id, THREAD_ID)

        assert isinstance(result, StatusResponse)
        assert result.status == "WAITING_ADMIN"
        assert result.thread_id == scoped_thread_id
        assert result.data is not None
        assert result.data["audit_log_id"] == audit.id
        assert result.data["risk_level"] == "HIGH"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_approve_returns_approved(self, db_session: AsyncSession):
        user = _make_user()
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        scoped_thread_id = build_thread_id(user.id, THREAD_ID)

        audit = AuditLog(
            user_id=user.id,
            thread_id=scoped_thread_id,
            action=AuditAction.APPROVE,
            trigger_type=AuditTriggerType.RISK,
            risk_level=RiskLevel.LOW,
            trigger_reason="risk",
            context_snapshot={},
            admin_comment="ok",
            reviewed_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
            refund_application_id=1,
            order_id=1,
        )
        db_session.add(audit)
        await db_session.commit()

        service = StatusService()
        result = await service.get_thread_status(db_session, user.id, THREAD_ID)

        assert isinstance(result, StatusResponse)
        assert result.status == "APPROVED"
        assert result.data is not None
        assert result.data["admin_comment"] == "ok"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_reject_returns_rejected(self, db_session: AsyncSession):
        user = _make_user()
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        scoped_thread_id = build_thread_id(user.id, THREAD_ID)

        audit = AuditLog(
            user_id=user.id,
            thread_id=scoped_thread_id,
            action=AuditAction.REJECT,
            trigger_type=AuditTriggerType.RISK,
            risk_level=RiskLevel.LOW,
            trigger_reason="risk",
            context_snapshot={},
            admin_comment="invalid",
            reviewed_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC),
            refund_application_id=1,
            order_id=1,
        )
        db_session.add(audit)
        await db_session.commit()

        service = StatusService()
        result = await service.get_thread_status(db_session, user.id, THREAD_ID)

        assert isinstance(result, StatusResponse)
        assert result.status == "REJECTED"
        assert result.message is not None
        assert "invalid" in result.message

    @pytest.mark.asyncio(loop_scope="session")
    async def test_no_audit_log_returns_processing(self, db_session: AsyncSession):
        user = _make_user()
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        scoped_thread_id = build_thread_id(user.id, THREAD_ID)

        message = MessageCard(
            thread_id=scoped_thread_id,
            message_type=MessageType.SYSTEM,
            status=MessageStatus.SENT,
            content={},
            sender_type="system",
            receiver_id=None,
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        db_session.add(message)
        await db_session.commit()

        service = StatusService()
        result = await service.get_thread_status(db_session, user.id, THREAD_ID)

        assert isinstance(result, StatusResponse)
        assert result.status == "PROCESSING"
        assert result.timestamp == "2024-01-01T12:00:00+00:00"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_no_audit_log_and_no_message_returns_processing_with_empty_timestamp(
        self, db_session: AsyncSession
    ):
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        service = StatusService()
        result = await service.get_thread_status(db_session, user.id, THREAD_ID)

        assert isinstance(result, StatusResponse)
        assert result.status == "PROCESSING"
        assert result.timestamp == ""
