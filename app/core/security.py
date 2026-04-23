# app/core/security.py
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.utils import utc_now

# 设置 Token 获取的 URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login", auto_error=False)


def extract_bearer_token(auth_header: str) -> str | None:
    if auth_header.lower().startswith("bearer ") and len(auth_header) > 7:
        return auth_header[7:]
    return None


def create_access_token(user_id: int, is_admin: bool = False) -> str:
    """
    生成 JWT Token

    Args:
        user_id: 用户ID
        is_admin:  是否为管理员
    """
    expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": utc_now(),
        "is_admin": is_admin,  # v4.0 新增：区分管理员权限
    }
    return jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )


def _decode_token(
    token: str,
    *,
    headers: dict[str, str] | None = None,
    missing_user_detail: str = "Invalid token: missing user ID",
) -> dict:
    """
    统一的 JWT decode、验证 sub 字段、处理异常。

    Args:
        token: JWT Token 字符串
        headers: 可选的响应头
        missing_user_detail: sub 缺失时的错误详情

    Returns:
        payload: 解析后的 JWT payload
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers=headers,
        )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=missing_user_detail,
                headers=headers,
            )

        return payload

    except jwt.ExpiredSignatureError as _err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers=headers,
        ) from _err
    except jwt.InvalidTokenError as _err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers=headers,
        ) from _err


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """
    FastAPI 依赖项：验证 Token 并提取 user_id
    """
    payload = _decode_token(
        token,
        headers={"WWW-Authenticate": "Bearer"},
        missing_user_detail="Invalid token:  missing user ID",
    )
    try:
        return int(payload["sub"])
    except (ValueError, TypeError) as _err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from _err


async def get_current_user_id_ws(token: str) -> int:
    """
    WebSocket Token 验证 (异步版本)

    Args:
        token: JWT Token 字符串

    Returns:
        user_id: 用户ID

    Raises:
        HTTPException: Token 无效时抛出
    """
    payload = _decode_token(token, missing_user_detail="Invalid token: missing user ID")
    try:
        return int(payload["sub"])
    except (ValueError, TypeError) as _err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
        ) from _err


def get_admin_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """
    管理员认证依赖项

    验证 Token 并检查管理员权限
    """
    return verify_admin_token(token)


def verify_admin_token(token: str) -> int:
    """
    验证管理员 Token（无需 FastAPI Depends，供 WebSocket 使用）

    验证 Token 并检查管理员权限
    """
    payload = _decode_token(token, headers={"WWW-Authenticate": "Bearer"})
    is_admin: bool = payload.get("is_admin", False)

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )

    try:
        return int(payload["sub"])
    except (ValueError, TypeError) as _err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from _err
