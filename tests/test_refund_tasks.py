from unittest.mock import AsyncMock, MagicMock, patch

from app.models.refund import RefundStatus
from app.tasks.refund_tasks import (
    notify_admin_audit,
    process_refund_payment,
    send_refund_sms,
)


def _make_async_session_mock():
    """构造一个支持 async with 的 mock session maker"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(return_value=session)
    async_cm.__aexit__ = AsyncMock(return_value=False)

    maker = MagicMock(return_value=async_cm)
    return maker, session


class TestSendRefundSms:
    def test_send_refund_sms_success(self):
        """直接调用 .run()，断言返回值包含 status=success"""
        result = send_refund_sms.run(1, "13800138000", "test")
        assert result["status"] == "success"
        assert result["refund_id"] == 1
        assert result["phone"] == "13800138000"


class TestProcessRefundPayment:
    def test_process_refund_payment_success(self):
        """mock async_session_maker 和 RefundApplication，验证状态被更新为 COMPLETED"""
        mock_refund = MagicMock()
        mock_refund.status = RefundStatus.PENDING
        mock_refund.updated_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_refund)

        maker, session = _make_async_session_mock()
        session.execute.return_value = mock_result

        with patch("app.tasks.refund_tasks.async_session_maker", maker):
            result = process_refund_payment.run(1, 99.9, "alipay")

        assert result["status"] == "success"
        assert result["refund_id"] == 1
        assert result["amount"] == 99.9
        assert mock_refund.status == RefundStatus.COMPLETED
        assert mock_refund.updated_at is not None
        session.add.assert_called_once_with(mock_refund)
        session.commit.assert_awaited_once()


class TestNotifyAdminAudit:
    def test_notify_admin_audit_success(self):
        """mock async_session_maker、AuditLog 和 MessageCard，验证消息被创建"""
        mock_audit = MagicMock()
        mock_audit.risk_level = "HIGH"
        mock_audit.trigger_reason = "金额过大"
        mock_audit.user_id = 100
        mock_audit.thread_id = "thread-abc"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_audit)

        maker, session = _make_async_session_mock()
        session.execute.return_value = mock_result

        mock_message_instance = MagicMock()

        with (
            patch("app.tasks.refund_tasks.async_session_maker", maker),
            patch(
                "app.tasks.refund_tasks.MessageCard",
                return_value=mock_message_instance,
            ) as mock_message_cls,
        ):
            result = notify_admin_audit.run(5)

        assert result["status"] == "success"
        assert result["audit_log_id"] == 5
        mock_message_cls.assert_called_once()
        call_kwargs = mock_message_cls.call_args.kwargs
        assert call_kwargs["thread_id"] == "thread-abc"
        assert call_kwargs["content"]["type"] == "admin_notification"
        assert call_kwargs["content"]["risk_level"] == "HIGH"
        session.add.assert_called_once_with(mock_message_instance)
        session.commit.assert_awaited_once()


def test_process_refund_payment_not_found():
    """退款记录不存在时抛出 ValueError 并重试"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)

    maker, session = _make_async_session_mock()
    session.execute.return_value = mock_result

    with patch("app.tasks.refund_tasks.async_session_maker", maker):
        # Celery 任务会在异常时调用 self.retry，但测试中 .run() 会直接抛出原始异常
        try:
            process_refund_payment.run(999, 99.9, "alipay")
            assert False, "应抛出异常"
        except ValueError as e:
            assert "Refund application 999 not found" in str(e)


def test_notify_admin_audit_not_found():
    """AuditLog 不存在时抛出 ValueError 并重试"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)

    maker, session = _make_async_session_mock()
    session.execute.return_value = mock_result

    with patch("app.tasks.refund_tasks.async_session_maker", maker):
        try:
            notify_admin_audit.run(999)
            assert False, "应抛出异常"
        except ValueError as e:
            assert "Audit log 999 not found" in str(e)


def test_notify_admin_audit_commit_exception():
    """数据库 commit 抛异常"""
    mock_audit = MagicMock()
    mock_audit.risk_level = "HIGH"
    mock_audit.trigger_reason = "金额过大"
    mock_audit.user_id = 100
    mock_audit.thread_id = "thread-abc"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_audit)

    maker, session = _make_async_session_mock()
    session.execute.return_value = mock_result
    session.commit = AsyncMock(side_effect=Exception("DB write failed"))

    with patch("app.tasks.refund_tasks.async_session_maker", maker):
        try:
            notify_admin_audit.run(5)
            assert False, "应抛出异常"
        except Exception as e:
            assert "DB write failed" in str(e)
