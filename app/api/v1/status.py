# app/api/v1/status.py
"""
状态查询 API
用于前端轮询获取 Agent 处理状态
"""

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.schemas.status import StatusResponse
from app.services.status_service import StatusService

router = APIRouter()


@router.get("/status/{thread_id}", response_model=StatusResponse)
async def get_thread_status(
    thread_id: str,
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    service: StatusService = Depends(StatusService),
):
    """
    获取会话状态

    用于 C 端轮询查询当前会话的处理状态
    """
    return await service.get_thread_status(session, current_user_id, thread_id)
