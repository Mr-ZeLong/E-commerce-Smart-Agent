from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.audit import AuditAction, AuditLog
from app.models.message import MessageCard
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User
from app.schemas.admin import TaskStatsResponse
from app.services.admin_service import AdminService, AuditAlreadyProcessedError, AuditNotFoundError


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

        service = AdminService(manager=mock_manager)
        with (
            patch("app.services.admin_service.process_refund_payment", mock_payment),
            patch("app.services.admin_service.send_refund_sms", mock_sms),
            patch("app.services.admin_service.build_thread_id", mock_build_thread_id),
        ):
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

        service = AdminService(manager=mock_manager)
        with (
            patch("app.services.admin_service.process_refund_payment", mock_payment),
            patch("app.services.admin_service.send_refund_sms", mock_sms),
            patch("app.services.admin_service.build_thread_id", mock_build_thread_id),
        ):
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
        mock_session.exec = AsyncMock(return_value=_make_exec_result(None))

        service = AdminService(manager=MagicMock())
        with pytest.raises(AuditNotFoundError):
            await service.process_admin_decision(
                mock_session,
                audit_log_id=999,
                action="APPROVE",
                admin_comment=None,
                current_admin_id=99,
            )

    @pytest.mark.asyncio
    async def test_400_for_already_processed(self):
        mock_session = AsyncMock()
        mock_audit_log = MagicMock(spec=AuditLog)
        mock_audit_log.action = AuditAction.APPROVE

        mock_session.exec = AsyncMock(return_value=_make_exec_result(mock_audit_log))

        service = AdminService(manager=MagicMock())
        with pytest.raises(AuditAlreadyProcessedError):
            await service.process_admin_decision(
                mock_session,
                audit_log_id=1,
                action="REJECT",
                admin_comment=None,
                current_admin_id=99,
            )


class TestQueryMethods:
    @pytest.mark.asyncio
    async def test_get_pending_tasks_without_filter(self):
        mock_session = AsyncMock()

        mock_log1 = MagicMock(spec=AuditLog)
        mock_log1.id = 1
        mock_log1.thread_id = "t1"
        mock_log1.user_id = 10
        mock_log1.refund_application_id = None
        mock_log1.order_id = None
        mock_log1.trigger_reason = "reason1"
        mock_log1.risk_level = "HIGH"
        mock_log1.context_snapshot = {}
        mock_log1.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        mock_log2 = MagicMock(spec=AuditLog)
        mock_log2.id = 2
        mock_log2.thread_id = "t2"
        mock_log2.user_id = 20
        mock_log2.refund_application_id = None
        mock_log2.order_id = None
        mock_log2.trigger_reason = "reason2"
        mock_log2.risk_level = "MEDIUM"
        mock_log2.context_snapshot = {}
        mock_log2.created_at.isoformat.return_value = "2024-01-02T00:00:00"

        result_mock = MagicMock()
        result_mock.all.return_value = [mock_log1, mock_log2]
        mock_session.exec = AsyncMock(return_value=result_mock)

        service = AdminService(manager=MagicMock())
        tasks = await service.get_pending_tasks(mock_session)

        assert len(tasks) == 2
        assert tasks[0].audit_log_id == 1
        assert tasks[1].audit_log_id == 2

    @pytest.mark.asyncio
    async def test_get_pending_tasks_with_risk_level_filter(self):
        mock_session = AsyncMock()

        mock_log = MagicMock(spec=AuditLog)
        mock_log.id = 1
        mock_log.thread_id = "t1"
        mock_log.user_id = 10
        mock_log.refund_application_id = None
        mock_log.order_id = None
        mock_log.trigger_reason = "reason"
        mock_log.risk_level = "HIGH"
        mock_log.context_snapshot = {}
        mock_log.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        result_mock = MagicMock()
        result_mock.all.return_value = [mock_log]
        mock_session.exec = AsyncMock(return_value=result_mock)

        service = AdminService(manager=MagicMock())
        tasks = await service.get_pending_tasks(mock_session, risk_level="HIGH")

        assert len(tasks) == 1
        assert tasks[0].risk_level == "HIGH"

    @pytest.mark.asyncio
    async def test_get_confidence_pending_tasks(self):
        mock_session = AsyncMock()

        mock_log = MagicMock(spec=AuditLog)
        mock_log.id = 1
        mock_log.thread_id = "t1"
        mock_log.user_id = 10
        mock_log.refund_application_id = None
        mock_log.order_id = None
        mock_log.trigger_reason = "reason"
        mock_log.risk_level = "LOW"
        mock_log.confidence_metadata = {"confidence_score": 0.45}
        mock_log.context_snapshot = {}
        mock_log.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        result_mock = MagicMock()
        result_mock.all.return_value = [mock_log]
        mock_session.exec = AsyncMock(return_value=result_mock)

        service = AdminService(manager=MagicMock())
        tasks = await service.get_confidence_pending_tasks(mock_session)

        assert len(tasks) == 1
        assert tasks[0].audit_log_id == 1
        assert "0.45" in tasks[0].trigger_reason

    @pytest.mark.asyncio
    async def test_get_all_pending_tasks(self):
        mock_session = AsyncMock()

        call_results = [
            MagicMock(one=MagicMock(return_value=2)),
            MagicMock(one=MagicMock(return_value=3)),
            MagicMock(one=MagicMock(return_value=1)),
        ]
        mock_session.exec = AsyncMock(side_effect=call_results)

        service = AdminService(manager=MagicMock())
        stats = await service.get_all_pending_tasks(mock_session)

        assert isinstance(stats, TaskStatsResponse)
        assert stats.risk_tasks == 2
        assert stats.confidence_tasks == 3
        assert stats.manual_tasks == 1
        assert stats.total == 6
