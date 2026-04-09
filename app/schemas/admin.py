from typing import Any, Literal

from pydantic import BaseModel


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
