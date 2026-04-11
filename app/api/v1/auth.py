# app/api/v1/auth.py
"""
认证 API - 登录、注册
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.limiter import limiter
from app.core.security import create_access_token, get_current_user_id
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserInfoResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
):
    """用户登录 - 验证用户名和密码，返回 JWT Token"""
    user = await service.authenticate_user(session, body.username, body.password)
    if user.id is None:
        raise HTTPException(status_code=500, detail="用户 ID 缺失，请联系管理员")
    token = create_access_token(user.id, is_admin=user.is_admin)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
    )


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
):
    user = await service.register_user(
        session,
        username=body.username,
        password=body.password,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
    )
    if user.id is None:
        raise HTTPException(status_code=500, detail="用户 ID 缺失，请联系管理员")
    token = create_access_token(user.id, is_admin=user.is_admin)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
):
    """获取当前登录用户信息"""
    user = await service.get_user_info(session, current_user_id)
    if user.id is None:
        raise HTTPException(status_code=500, detail="用户 ID 缺失，请联系管理员")
    return UserInfoResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
    )
