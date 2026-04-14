# app/tasks/refund_tasks.py
"""
退款相关异步任务
"""

import logging
import time
from typing import Any

from sqlmodel import select

from app.celery_app import celery_app
from app.core.database import sync_session_maker
from app.core.utils import utc_now
from app.models.audit import AuditLog
from app.models.message import MessageCard, MessageStatus, MessageType
from app.models.refund import RefundApplication, RefundStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="refund.send_sms", max_retries=3, default_retry_delay=60)
def send_refund_sms(_self, refund_id: int, phone: str, message: str) -> dict[str, Any]:
    logger.info(f"📱 [SMS] 发送短信到 {phone}: {message}")
    return {
        "status": "success",
        "refund_id": refund_id,
        "phone": phone,
        "sent_at": utc_now().isoformat(),
    }


@celery_app.task(
    bind=True,
    name="refund.process_payment",
    max_retries=3,
    default_retry_delay=120,
)
def process_refund_payment(
    self, refund_id: int, amount: float, payment_method: str
) -> dict[str, Any]:
    with sync_session_maker() as session:
        result = session.exec(select(RefundApplication).where(RefundApplication.id == refund_id))
        refund = result.one_or_none()

        if not refund:
            exc = ValueError(f"Refund application {refund_id} not found")
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                raise exc

        logger.info(f"💰 [Payment] 退款 ¥{amount} 到 {payment_method}")

        refund.status = RefundStatus.COMPLETED
        refund.updated_at = utc_now()
        session.add(refund)
        session.commit()

        return {
            "status": "success",
            "refund_id": refund_id,
            "amount": amount,
            "transaction_id": f"TXN{refund_id}{int(time.time())}",
            "completed_at": utc_now().isoformat(),
        }


@celery_app.task(bind=True, name="refund.notify_admin", max_retries=2)
def notify_admin_audit(self, audit_log_id: int) -> dict[str, Any]:
    with sync_session_maker() as session:
        result = session.exec(select(AuditLog).where(AuditLog.id == audit_log_id))
        audit_log = result.one_or_none()

        if not audit_log:
            exc = ValueError(f"Audit log {audit_log_id} not found")
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                raise exc

        logger.info("  [Notify] 通知管理员审核任务:")
        logger.info(f"  - 风险等级: {audit_log.risk_level}")
        logger.info(f"  - 触发原因: {audit_log.trigger_reason}")
        logger.info(f"  - 用户ID: {audit_log.user_id}")

        message = MessageCard(
            thread_id=audit_log.thread_id,
            message_type=MessageType.SYSTEM,
            status=MessageStatus.SENT,
            content={
                "type": "admin_notification",
                "audit_log_id": audit_log_id,
                "risk_level": audit_log.risk_level,
                "message": f"新的{audit_log.risk_level}风险审核任务",
            },
            sender_type="system",
            receiver_id=None,
        )
        session.add(message)
        session.commit()

        return {
            "status": "success",
            "audit_log_id": audit_log_id,
            "notified_at": utc_now().isoformat(),
        }
