# app/api/v1/admin.py
"""
管理员 API
"""
from collections.abc import Sequence
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.core.utils import utc_now
from app.models.audit import AuditAction, AuditLog, AuditTriggerType
from app.models.message import MessageCard, MessageStatus, MessageType
from app.models.refund import RefundApplication, RefundStatus
from app.tasks.refund_tasks import process_refund_payment, send_refund_sms
from app.websocket.manager import manager

router = APIRouter()


class AuditTask(BaseModel):
    """审核任务"""
    audit_log_id: int
    thread_id: str
    user_id: int
    refund_application_id: int | None
    order_id: int | None
    trigger_reason: str
    risk_level: str
    context_snapshot: dict[str, Any]
    created_at: str


class AdminDecisionRequest(BaseModel):
    """管理员决策请求"""
    action: Literal["APPROVE", "REJECT"]
    admin_comment: str | None = None


class AdminDecisionResponse(BaseModel):
    """管理员决策响应"""
    success: bool
    message: str
    audit_log_id: int
    action: str


class TaskStatsResponse(BaseModel):
    """任务统计响应"""
    risk_tasks: int
    confidence_tasks: int
    manual_tasks: int
    total: int


def _build_audit_task(log: AuditLog, trigger_reason: str | None = None) -> AuditTask:
    """将 AuditLog 转换为 AuditTask"""
    return AuditTask(
        audit_log_id=log.id,  # type: ignore
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
    """将 AuditLog 列表转换为 AuditTask 列表"""
    return [_build_audit_task(log) for log in audit_logs]


async def _count_pending_by_trigger(session, trigger_type: AuditTriggerType) -> int:
    """统计指定触发类型的待审核任务数量"""
    stmt = select(func.count()).select_from(AuditLog).where(
        AuditLog.action == AuditAction.PENDING,
        AuditLog.trigger_type == trigger_type
    )
    result = await session.exec(stmt)
    return result.one()


@router.get("/admin/tasks", response_model=list[AuditTask])
async def get_pending_tasks(
    risk_level: str | None = None,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session)
):
    """
    获取待审核任务列表

    Query Params:
        risk_level: 可选，筛选风险等级 (HIGH, MEDIUM, LOW)
    """
    # 构建查询
    stmt = select(AuditLog).where(  # type: ignore[var-annotated]
        AuditLog.action == AuditAction.PENDING
    ).order_by(desc(AuditLog.created_at))

    if risk_level:
        stmt = stmt.where(AuditLog.risk_level == risk_level)

    result = await session.exec(stmt)
    audit_logs = result.all()

    return _build_audit_tasks(audit_logs)


@router.get("/admin/confidence-tasks", response_model=list[AuditTask])
async def get_confidence_pending_tasks(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session)
):
    """获取置信度触发的待审核任务"""
    stmt = select(AuditLog).where(
        AuditLog.action == AuditAction.PENDING,
        AuditLog.trigger_type == AuditTriggerType.CONFIDENCE
    ).order_by(desc(AuditLog.created_at))

    result = await session.exec(stmt)
    audit_logs = result.all()

    tasks = []
    for log in audit_logs:
        confidence_meta = log.confidence_metadata or {}
        tasks.append(_build_audit_task(
            log,
            trigger_reason=f"置信度不足: {confidence_meta.get('confidence_score', 0):.2f}"
        ))
    return tasks


@router.get("/admin/tasks-all", response_model=TaskStatsResponse)
async def get_all_pending_tasks(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session)
):
    """获取所有待审核任务（风险 + 置信度 + 手动）"""
    risk_count = await _count_pending_by_trigger(session, AuditTriggerType.RISK)
    conf_count = await _count_pending_by_trigger(session, AuditTriggerType.CONFIDENCE)
    manual_count = await _count_pending_by_trigger(session, AuditTriggerType.MANUAL)

    return TaskStatsResponse(
        risk_tasks=risk_count,
        confidence_tasks=conf_count,
        manual_tasks=manual_count,
        total=risk_count + conf_count + manual_count
    )


@router.post("/admin/resume/{audit_log_id}", response_model=AdminDecisionResponse)
async def admin_decision(
    audit_log_id: int,
    request: AdminDecisionRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session)
):
    """
    管理员决策接口

    Path Params:
        audit_log_id: 审计日志ID

    Body:
        action:  APPROVE | REJECT
        admin_comment:  管理员备注
    """
    # 1. 查询审计日志
    result = await session.exec(
        select(AuditLog).where(AuditLog.id == audit_log_id)
    )
    audit_log = result.one_or_none()

    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    if audit_log.action != AuditAction.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This audit has already been processed"
        )

    # 2. 更新审计日志
    action_enum = AuditAction.APPROVE if request.action == "APPROVE" else AuditAction.REJECT
    audit_log.action = action_enum
    audit_log.admin_id = current_admin_id
    audit_log.admin_comment = request.admin_comment
    audit_log.reviewed_at = utc_now()

    session.add(audit_log)

    # 3. 更新退款申请状态
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
                refund.admin_note = request.admin_comment
                refund.reviewed_by = current_admin_id
                refund.reviewed_at = utc_now()

                # 4. 触发异步任务：退款 + 短信通知
                process_refund_payment.delay(
                    refund_id=refund.id,
                    amount=float(refund.refund_amount),
                    payment_method="原支付方式"
                )

                send_refund_sms.delay(
                    refund_id=refund.id,
                    phone="138****1234",  # TODO: 从用户表获取
                    message=f"您的退款申请已通过，退款金额¥{refund.refund_amount}将在3-5个工作日退回。"
                )

            else:
                refund.status = RefundStatus.REJECTED
                refund.admin_note = request.admin_comment
                refund.reviewed_by = current_admin_id
                refund.reviewed_at = utc_now()

            session.add(refund)

    # 5. 创建状态变更消息卡片
    status_message = " 审核通过，资金将在3-5个工作日内原路退回" if action_enum == AuditAction.APPROVE else f" 审核未通过: {request.admin_comment}"

    message_card = MessageCard(
        thread_id=audit_log.thread_id,
        message_type=MessageType.AUDIT_CARD,
        status=MessageStatus.SENT,
        content={
            "card_type": "audit_result",
            "action": request.action,
            "message": status_message,
            "admin_comment": request.admin_comment,
            "timestamp": utc_now().isoformat(),
        },
        sender_type="admin",
        sender_id=current_admin_id,
        receiver_id=audit_log.user_id,
    )
    session.add(message_card)

    await session.commit()

    # 6. 通过 WebSocket 实时推送状态变更
    await manager.notify_status_change(
        thread_id=audit_log.thread_id,
        status=request.action,
        data={
            "message": status_message,
            "admin_comment": request.admin_comment,
        }
    )

    return AdminDecisionResponse(
        success=True,
        message=f"审核决策已提交:  {request.action}",
        audit_log_id=audit_log_id,
        action=request.action,
    )
