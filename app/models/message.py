# app/models/message.py
"""
v4.0 新增：结构化消息模型
支持富媒体卡片渲染（audit_card, order_card, text）
"""
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, String, text
from sqlmodel import Field, SQLModel

from app.core.utils import naive_utc_now, utc_now


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"                    # 普通文本消息
    AUDIT_CARD = "audit_card"        # 人工审核卡片
    ORDER_CARD = "order_card"        # 订单信息卡片
    REFUND_CARD = "refund_card"      # 退款进度卡片
    SYSTEM = "system"                # 系统通知
    CONFIDENCE_CARD = "confidence_card"  # 置信度信息卡片 (v4.1新增)
    TRANSFER_CARD = "transfer_card"      # 转人工信息卡片 (v4.1新增)


class MessageStatus(str, Enum):
    """消息状态"""
    PENDING = "pending"              # 待处理
    SENT = "sent"                    # 已发送
    READ = "read"                    # 已读
    FAILED = "failed"                # 发送失败


class MessageCard(SQLModel, table=True):
    """结构化消息表 - 支持富媒体卡片"""
    __tablename__ = "message_cards"

    id: int | None = Field(default=None, primary_key=True)

    # 会话标识
    thread_id: str = Field(index=True, max_length=128, description="会话ID")

    # 消息类型
    message_type: MessageType = Field(
        default=MessageType.TEXT,
        sa_column=Column(String, index=True, nullable=False)
    )

    # 消息状态
    status: MessageStatus = Field(
        default=MessageStatus.PENDING,
        sa_column=Column(String, index=True, nullable=False)
    )

    # 消息内容 (JSON格式，支持富媒体)
    content: dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
        description="消息内容，JSON格式"
    )

    # 发送者 (user_id 或 system)
    sender_id: int | None = Field(default=None, index=True)
    sender_type: str = Field(default="user", max_length=32)  # user | agent | admin | system

    # 接收者
    receiver_id: int | None = Field(default=None, index=True)

    # 元数据（可扩展）
    meta_data: dict[str, Any] | None = Field(default={}, sa_column=Column(JSON))

    # 时间戳
    created_at: datetime = Field(
        default_factory=naive_utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )

    updated_at: datetime = Field(
        default_factory=naive_utc_now,
        sa_column_kwargs={
            "server_default": text("CURRENT_TIMESTAMP"),
            "onupdate": text("CURRENT_TIMESTAMP")
        }
    )

    model_config = {"use_enum_values": True}
