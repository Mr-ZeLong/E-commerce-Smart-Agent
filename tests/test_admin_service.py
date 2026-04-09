from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.models.audit import AuditAction, AuditLog
from app.models.message import MessageCard
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User
from app.services.admin_service import AdminService


def _make_exec_result(obj):
    m = MagicMock()
    m.one_or_none.return_value = obj
    return m


class TestProcessAdminDecision:
    @pytest.mark.asyncio
    async def test_approve_with_refund(self):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_audit_log = MagicMock(spec=AuditLog)
        mock_audit_log.id = 1
        mock_audit_log.action = AuditAction.PENDING
        mock_audit_log.user_id = 10
        mock_audit_log.thread_id = "10__thread"
        mock_audit_log.refund_application_id = 100
        mock_audit_log.order_id = 50
        mock_audit_log.trigger_reason = "risk"
        mock_audit_log.risk_level = "HIGH"
        mock_audit_log.context_snapshot = {}

        mock_user = MagicMock(spec=User)
        mock_user.phone = "13800138000"

        mock_refund = MagicMock(spec=RefundApplication)
        mock_refund.id = 100
        mock_refund.refund_amount = 199.99

        mock_session.exec = AsyncMock(
            side_effect=[
                _make_exec_result(mock_audit_log),
                _make_exec_result(mock_user),
                _make_exec_result(mock_refund),
            ]
        )

        mock_payment = MagicMock()
        mock_sms = MagicMock()
        mock_manager = AsyncMock()
        mock_build_thread_id = MagicMock(return_value="built_thread")

        service = AdminService(
            process_refund_payment=mock_payment,
            send_refund_sms=mock_sms,
            manager=mock_manager,
            build_thread_id=mock_build_thread_id,
        )

        result = await service.process_admin_decision(
            mock_session,
            audit_log_id=1,
            action="APPROVE",
            admin_comment="Approved",
            current_admin_id=99,
        )

        assert result.success is True
        assert result.action == "APPROVE"
        assert mock_audit_log.action == AuditAction.APPROVE
        assert mock_audit_log.admin_id == 99
        assert mock_audit_log.admin_comment == "Approved"
        assert mock_audit_log.reviewed_at is not None

        assert mock_refund.status == RefundStatus.APPROVED
        assert mock_refund.reviewed_by == 99
        assert mock_refund.reviewed_at is not None

        mock_payment.delay.assert_called_once_with(
            refund_id=100, amount=199.99, payment_method="原支付方式"
        )
        mock_sms.delay.assert_called_once_with(
            refund_id=100,
            phone="13800138000",
            message="您的退款申请已通过，退款金额¥199.99将在3-5个工作日退回。",
        )
        mock_manager.notify_status_change.assert_awaited_once_with(
            thread_id="built_thread",
            status="APPROVE",
            data={
                "message": " 审核通过，资金将在3-5个工作日内原路退回",
                "admin_comment": "Approved",
            },
        )

        added_objects = [call[0][0] for call in mock_session.add.call_args_list]
        assert any(isinstance(obj, MessageCard) for obj in added_objects)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_with_refund(self):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_audit_log = MagicMock(spec=AuditLog)
        mock_audit_log.id = 2
        mock_audit_log.action = AuditAction.PENDING
        mock_audit_log.user_id = 10
        mock_audit_log.thread_id = "10__thread"
        mock_audit_log.refund_application_id = 100
        mock_audit_log.order_id = 50
        mock_audit_log.trigger_reason = "risk"
        mock_audit_log.risk_level = "HIGH"
        mock_audit_log.context_snapshot = {}

        mock_user = MagicMock(spec=User)
        mock_user.phone = "13800138000"

        mock_refund = MagicMock(spec=RefundApplication)
        mock_refund.id = 100
        mock_refund.refund_amount = 199.99

        mock_session.exec = AsyncMock(
            side_effect=[
                _make_exec_result(mock_audit_log),
                _make_exec_result(mock_user),
                _make_exec_result(mock_refund),
            ]
        )

        mock_payment = MagicMock()
        mock_sms = MagicMock()
        mock_manager = AsyncMock()
        mock_build_thread_id = MagicMock(return_value="built_thread")

        service = AdminService(
            process_refund_payment=mock_payment,
            send_refund_sms=mock_sms,
            manager=mock_manager,
            build_thread_id=mock_build_thread_id,
        )

        result = await service.process_admin_decision(
            mock_session,
            audit_log_id=2,
            action="REJECT",
            admin_comment="Rejected",
            current_admin_id=99,
        )

        assert result.success is True
        assert result.action == "REJECT"
        assert mock_audit_log.action == AuditAction.REJECT
        assert mock_audit_log.admin_id == 99
        assert mock_refund.status == RefundStatus.REJECTED
        assert mock_refund.reviewed_by == 99

        mock_payment.delay.assert_not_called()
        mock_sms.delay.assert_not_called()
        mock_manager.notify_status_change.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_404_for_missing_audit_log(self):
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            return_value=_make_exec_result(None)
        )

        service = AdminService()
        with pytest.raises(HTTPException) as exc_info:
            await service.process_admin_decision(
                mock_session,
                audit_log_id=999,
                action="APPROVE",
                admin_comment=None,
                current_admin_id=99,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Audit log not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_400_for_already_processed(self):
        mock_session = AsyncMock()
        mock_audit_log = MagicMock(spec=AuditLog)
        mock_audit_log.action = AuditAction.APPROVE

        mock_session.exec = AsyncMock(
            return_value=_make_exec_result(mock_audit_log)
        )

        service = AdminService()
        with pytest.raises(HTTPException) as exc_info:
            await service.process_admin_decision(
                mock_session,
                audit_log_id=1,
                action="REJECT",
                admin_comment=None,
                current_admin_id=99,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already been processed" in exc_info.value.detail
