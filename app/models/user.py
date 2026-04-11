# app/models/user.py
"""
用户模型 - 支持真实登录认证
"""

from datetime import datetime

import bcrypt
from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class User(SQLModel, table=True):
    """用户表"""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)

    # 用户名（登录凭证）
    username: str = Field(index=True, unique=True, max_length=50, description="用户名")

    # 密码哈希
    password_hash: str = Field(max_length=255, description="密码哈希")

    # 用户信息
    email: str = Field(unique=True, index=True, description="邮箱")
    full_name: str = Field(max_length=100, description="真实姓名")
    phone: str | None = Field(default=None, max_length=20, description="手机号")

    # 角色权限
    is_admin: bool = Field(default=False, description="是否为管理员")
    is_active: bool = Field(default=True, description="账号是否激活")

    # 时间戳
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )

    @staticmethod
    def hash_password(password: str) -> str:
        """密码加密"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "alice",
                "email": "alice@example.com",
                "full_name": "Alice Wang",
            }
        }
    }
