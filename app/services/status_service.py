# app/services/status_service.py
"""Status determination business logic service."""

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.utils import build_thread_id
from app.models.audit import AuditAction, AuditLog
from app.models.message import MessageCard
from app.schemas.status import StatusResponse


class StatusService:
    """Service layer for thread status queries."""

    async def get_thread_status(
        self,
        session: AsyncSession,
        user_id: int,
        thread_id: str,
    ) -> StatusResponse:
        """
        Query the latest audit log and message for a thread and map
        the audit action to a frontend-friendly status.
        """
        scoped_thread_id = build_thread_id(user_id, thread_id)

        # 1. Query the latest audit log for this user + scoped thread_id
        audit_result = await session.exec(
            select(AuditLog)
            .where(AuditLog.thread_id == scoped_thread_id)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .limit(1)
        )
        latest_audit = audit_result.first()

        # 2. Query the latest message for this scoped thread_id
        message_result = await session.exec(
            select(MessageCard)
            .where(MessageCard.thread_id == scoped_thread_id)
            .order_by(desc(MessageCard.created_at))
            .limit(1)
        )
        latest_message = message_result.first()

        # 3. Map audit action to status response
        if latest_audit:
            if latest_audit.action == AuditAction.PENDING:
                return StatusResponse(
                    thread_id=scoped_thread_id,
                    status="WAITING_ADMIN",
                    message="人工审核中，请稍候.. .",
                    data={
                        "audit_log_id": latest_audit.id,
                        "risk_level": latest_audit.risk_level,
                        "trigger_reason": latest_audit.trigger_reason,
                    },
                    timestamp=latest_audit.created_at.isoformat()
                )
            elif latest_audit.action == AuditAction.APPROVE:
                return StatusResponse(
                    thread_id=scoped_thread_id,
                    status="APPROVED",
                    message="审核通过，正在处理退款.. .",
                    data={
                        "admin_comment": latest_audit.admin_comment,
                        "reviewed_at": latest_audit.reviewed_at.isoformat() if latest_audit.reviewed_at else None,
                    },
                    timestamp=latest_audit.updated_at.isoformat()
                )
            elif latest_audit.action == AuditAction.REJECT:
                return StatusResponse(
                    thread_id=scoped_thread_id,
                    status="REJECTED",
                    message=f"审核未通过:  {latest_audit.admin_comment or '请联系客服'}",
                    data={
                        "admin_comment": latest_audit.admin_comment,
                        "reviewed_at": latest_audit.reviewed_at.isoformat() if latest_audit.reviewed_at else None,
                    },
                    timestamp=latest_audit.updated_at.isoformat()
                )

        # 4. No audit log found – return PROCESSING
        return StatusResponse(
            thread_id=scoped_thread_id,
            status="PROCESSING",
            message="正在处理您的请求...",
            data={},
            timestamp=latest_message.created_at.isoformat() if latest_message else ""
        )
