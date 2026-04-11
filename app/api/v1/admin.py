"""
管理员 API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.schemas.admin import (
    AdminDecisionRequest,
    AdminDecisionResponse,
    AuditTask,
    TaskStatsResponse,
)
from app.services.admin_service import AdminService, AuditAlreadyProcessedError, AuditNotFoundError

router = APIRouter()


@router.get("/admin/tasks", response_model=list[AuditTask])
async def get_pending_tasks(
    risk_level: str | None = None,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(AdminService),
):
    """获取待审核任务列表"""
    return await service.get_pending_tasks(session, risk_level)


@router.get("/admin/confidence-tasks", response_model=list[AuditTask])
async def get_confidence_pending_tasks(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(AdminService),
):
    """获取置信度触发的待审核任务"""
    return await service.get_confidence_pending_tasks(session)


@router.get("/admin/tasks-all", response_model=TaskStatsResponse)
async def get_all_pending_tasks(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(AdminService),
):
    """获取所有待审核任务（风险 + 置信度 + 手动）"""
    return await service.get_all_pending_tasks(session)


@router.post("/admin/resume/{audit_log_id}", response_model=AdminDecisionResponse)
async def admin_decision(
    audit_log_id: int,
    request: AdminDecisionRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(AdminService),
):
    """管理员决策接口"""
    try:
        return await service.process_admin_decision(
            session, audit_log_id, request.action, request.admin_comment, current_admin_id
        )
    except AuditNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found",
        )
    except AuditAlreadyProcessedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This audit has already been processed",
        )
