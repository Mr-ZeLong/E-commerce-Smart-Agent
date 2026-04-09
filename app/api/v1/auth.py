# app/api/v1/auth.py
"""
认证 API - 登录、注册
"""

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.limiter import limiter
from app.core.security import get_current_user_id
from app.services.auth_service import AuthService, create_user_token

router = APIRouter()
auth_service = AuthService()


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    email: EmailStr = Field(..., description="邮箱")
    full_name: str = Field(..., min_length=2, max_length=100, description="真实姓名")
    phone: str | None = Field(default=None, description="手机号")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    full_name: str
    is_admin: bool


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: int
    username: str
    email: str
    full_name: str
    phone: str | None
    is_admin: bool
    created_at: str


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """用户登录 - 验证用户名和密码，返回 JWT Token"""
    user = await auth_service.authenticate_user(session, body.username, body.password)
    token = create_user_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,  # type: ignore[arg-type]
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
):
    """用户注册 - 创建新用户并返回 JWT Token"""
    user = await auth_service.register_user(session, body)
    token = create_user_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,  # type: ignore[arg-type]
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前登录用户信息"""
    return await auth_service.get_user_info(session, current_user_id)
