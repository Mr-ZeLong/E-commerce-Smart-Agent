import logging
from collections.abc import Sequence

from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.utils import utc_now
from app.models.audit import AuditAction, AuditLog, AuditTriggerType
from app.models.message import MessageCard, MessageStatus, MessageType
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User
from app.schemas.admin import AdminDecisionResponse, AuditTask, TaskStatsResponse
from app.tasks.refund_tasks import process_refund_payment, send_refund_sms
from app.websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)


class AuditNotFoundError(Exception):
    pass


class AuditAlreadyProcessedError(Exception):
    pass


class AdminService:
    def __init__(self, manager: ConnectionManager | None = None):
        self.manager = manager

    async def get_pending_tasks(
        self, session: AsyncSession, risk_level: str | None = None
    ) -> list[AuditTask]:
        """获取待审核任务列表"""
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == AuditAction.PENDING)
            .order_by(desc(AuditLog.created_at))
        )

        if risk_level:
            stmt = stmt.where(AuditLog.risk_level == risk_level)

        result = await session.exec(stmt)
        audit_logs = result.all()

        return _build_audit_tasks(audit_logs)

    async def get_confidence_pending_tasks(self, session: AsyncSession) -> list[AuditTask]:
        """获取置信度触发的待审核任务"""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.action == AuditAction.PENDING,
                AuditLog.trigger_type == AuditTriggerType.CONFIDENCE,
            )
            .order_by(desc(AuditLog.created_at))
        )

        result = await session.exec(stmt)
        audit_logs = result.all()

        tasks = []
        for log in audit_logs:
            confidence_meta = log.confidence_metadata or {}
            tasks.append(
                _build_audit_task(
                    log,
                    trigger_reason=f"置信度不足: {confidence_meta.get('confidence_score', 0):.2f}",
                )
            )
        return tasks

    async def get_all_pending_tasks(self, session: AsyncSession) -> TaskStatsResponse:
        """获取所有待审核任务（风险 + 置信度 + 手动）"""
        risk_count = await _count_pending_by_trigger(session, AuditTriggerType.RISK)
        conf_count = await _count_pending_by_trigger(session, AuditTriggerType.CONFIDENCE)
        manual_count = await _count_pending_by_trigger(session, AuditTriggerType.MANUAL)

        return TaskStatsResponse(
            risk_tasks=risk_count,
            confidence_tasks=conf_count,
            manual_tasks=manual_count,
            total=risk_count + conf_count + manual_count,
        )

    async def process_admin_decision(
        self,
        session: AsyncSession,
        audit_log_id: int,
        action: str,
        admin_comment: str | None,
        current_admin_id: int,
    ) -> AdminDecisionResponse:
        """处理管理员决策"""
        result = await session.exec(
            select(AuditLog).where(AuditLog.id == audit_log_id).with_for_update()
        )
        audit_log = result.one_or_none()

        if not audit_log:
            raise AuditNotFoundError()

        if audit_log.action != AuditAction.PENDING:
            raise AuditAlreadyProcessedError()

        action_enum = AuditAction.APPROVE if action == "APPROVE" else AuditAction.REJECT
        audit_log.action = action_enum
        audit_log.admin_id = current_admin_id
        audit_log.admin_comment = admin_comment
        audit_log.reviewed_at = utc_now()

        session.add(audit_log)

        user_result = await session.exec(select(User).where(User.id == audit_log.user_id))
        user = user_result.one_or_none()
        phone = user.phone if user else None

        payment_task_kwargs: dict[str, object] | None = None
        sms_task_kwargs: dict[str, object] | None = None

        if audit_log.refund_application_id:
            refund_result = await session.exec(
                select(RefundApplication).where(
                    RefundApplication.id == audit_log.refund_application_id
                )
            )
            refund = refund_result.one_or_none()

            if refund:
                if action_enum == AuditAction.APPROVE:
                    refund.status = RefundStatus.APPROVED
                    refund.admin_note = admin_comment
                    refund.reviewed_by = current_admin_id
                    refund.reviewed_at = utc_now()

                    payment_task_kwargs = {
                        "refund_id": refund.id,
                        "amount": float(refund.refund_amount),
                        "payment_method": "原支付方式",
                    }

                    if phone:
                        sms_task_kwargs = {
                            "refund_id": refund.id,
                            "phone": phone,
                            "message": f"您的退款申请已通过，退款金额¥{refund.refund_amount}将在3-5个工作日退回。",
                        }

                else:
                    refund.status = RefundStatus.REJECTED
                    refund.admin_note = admin_comment
                    refund.reviewed_by = current_admin_id
                    refund.reviewed_at = utc_now()

                session.add(refund)

        status_message = (
            " 审核通过，资金将在3-5个工作日内原路退回"
            if action_enum == AuditAction.APPROVE
            else f" 审核未通过: {admin_comment}"
        )

        message_card = MessageCard(
            thread_id=audit_log.thread_id,
            message_type=MessageType.AUDIT_CARD,
            status=MessageStatus.SENT,
            content={
                "card_type": "audit_result",
                "action": action,
                "message": status_message,
                "admin_comment": admin_comment,
                "timestamp": utc_now().isoformat(),
            },
            sender_type="admin",
            sender_id=current_admin_id,
            receiver_id=audit_log.user_id,
        )
        session.add(message_card)

        await session.commit()

        if payment_task_kwargs is not None:
            process_refund_payment.delay(**payment_task_kwargs)
        if sms_task_kwargs is not None:
            send_refund_sms.delay(**sms_task_kwargs)

        if self.manager is not None:
            try:
                await self.manager.notify_status_change(
                    thread_id=audit_log.thread_id,
                    status=action,
                    data={
                        "message": status_message,
                        "admin_comment": admin_comment,
                    },
                )
            except (RuntimeError, ConnectionError):
                logger.exception("Failed to notify status change via WebSocket")

        return AdminDecisionResponse(
            success=True,
            message=f"审核决策已提交:  {action}",
            audit_log_id=audit_log_id,
            action=action,
        )


def _build_audit_task(log: AuditLog, trigger_reason: str | None = None) -> AuditTask:
    if log.id is None:
        raise RuntimeError("Audit log ID is missing after creation")
    return AuditTask(
        audit_log_id=log.id,
        thread_id=log.thread_id,
        user_id=log.user_id,
        refund_application_id=log.refund_application_id,
        order_id=log.order_id,
        trigger_reason=trigger_reason if trigger_reason is not None else log.trigger_reason,
        risk_level=log.risk_level,
        context_snapshot=log.context_snapshot,
        created_at=log.created_at.isoformat(),
    )


def _build_audit_tasks(audit_logs: Sequence[AuditLog]) -> list[AuditTask]:
    return [_build_audit_task(log) for log in audit_logs]


async def _count_pending_by_trigger(session: AsyncSession, trigger_type: AuditTriggerType) -> int:
    stmt = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == AuditAction.PENDING, AuditLog.trigger_type == trigger_type)
    )
    result = await session.exec(stmt)
    return result.one()
