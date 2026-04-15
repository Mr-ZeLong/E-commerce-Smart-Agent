import uuid
from decimal import Decimal

import pytest
from sqlmodel import select

from app.models.audit import AuditAction, AuditLog, AuditTriggerType, RiskLevel
from app.models.message import MessageCard, MessageType
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User
from app.tasks.refund_tasks import (
    notify_admin_audit,
    process_refund_payment,
    send_refund_sms,
)


class TestSendRefundSms:
    def test_send_refund_sms_success(self):
        result = send_refund_sms.run(1, "13800138000", "test")
        assert result["status"] == "success"
        assert result["refund_id"] == 1
        assert result["phone"] == "13800138000"


class TestProcessRefundPayment:
    def test_process_refund_payment_success(self, db_sync_session):
        user = User(
            username=f"refund_user_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("testpass"),
            email=f"{uuid.uuid4().hex[:8]}@test.com",
            full_name="Test User",
        )
        db_sync_session.add(user)
        db_sync_session.commit()
        db_sync_session.refresh(user)
        assert user.id is not None

        order = Order(
            order_sn=f"ORD{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id,
            status=OrderStatus.DELIVERED,
            total_amount=Decimal("199.99"),
            shipping_address="Test Address",
        )
        db_sync_session.add(order)
        db_sync_session.commit()
        db_sync_session.refresh(order)
        assert order.id is not None

        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            status=RefundStatus.PENDING,
            reason_detail="Test refund",
            refund_amount=Decimal("99.9"),
        )
        db_sync_session.add(refund)
        db_sync_session.commit()
        db_sync_session.refresh(refund)

        result = process_refund_payment.run(refund.id, 99.9, "alipay", session=db_sync_session)

        assert result["status"] == "success"
        assert result["refund_id"] == refund.id
        assert result["amount"] == 99.9

        updated = db_sync_session.exec(
            select(RefundApplication).where(RefundApplication.id == refund.id)
        ).one()
        assert updated.status == RefundStatus.COMPLETED
        assert updated.updated_at is not None


def test_process_refund_payment_not_found(db_sync_session):
    with pytest.raises(ValueError, match="Refund application 999 not found"):
        process_refund_payment.run(999, 99.9, "alipay", session=db_sync_session)


class TestNotifyAdminAudit:
    def test_notify_admin_audit_success(self, db_sync_session):
        user = User(
            username=f"audit_user_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("testpass"),
            email=f"{uuid.uuid4().hex[:8]}@test.com",
            full_name="Test User",
        )
        db_sync_session.add(user)
        db_sync_session.commit()
        db_sync_session.refresh(user)
        assert user.id is not None

        log = AuditLog(
            thread_id=f"thread-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            trigger_reason="金额过大",
            risk_level=RiskLevel.HIGH,
            action=AuditAction.PENDING,
            trigger_type=AuditTriggerType.RISK,
            context_snapshot={},
        )
        db_sync_session.add(log)
        db_sync_session.commit()
        db_sync_session.refresh(log)

        result = notify_admin_audit.run(log.id, session=db_sync_session)

        assert result["status"] == "success"
        assert result["audit_log_id"] == log.id

        message = db_sync_session.exec(
            select(MessageCard).where(MessageCard.thread_id == log.thread_id)
        ).one_or_none()
        assert message is not None
        assert message.message_type == MessageType.SYSTEM
        assert message.content["type"] == "admin_notification"
        assert message.content["risk_level"] == RiskLevel.HIGH


def test_notify_admin_audit_not_found(db_sync_session):
    with pytest.raises(ValueError, match="Audit log 999 not found"):
        notify_admin_audit.run(999, session=db_sync_session)
