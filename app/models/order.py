# app/models/order.py
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, Numeric, String, text
from sqlmodel import Field, SQLModel

from app.core.utils import naive_utc_now


# 1. 使用 Enum 管理状态
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# 2. 订单模型
class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    order_sn: str = Field(unique=True, index=True, max_length=32)

    # 关联用户 - 只用外键，避免循环导入
    user_id: int = Field(foreign_key="users.id", ondelete="RESTRICT")

    status: OrderStatus = Field(
        default=OrderStatus.PENDING, sa_column=Column(String, index=True, nullable=False)
    )

    total_amount: float = Field(sa_column=Column(Numeric(precision=10, scale=2)))
    items: list[dict] = Field(default=[], sa_column=Column(JSON))

    tracking_number: str | None = Field(default=None, index=True)
    shipping_address: str = Field(description="下单时的详细地址快照")

    created_at: datetime = Field(
        default_factory=naive_utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )

    updated_at: datetime = Field(
        default_factory=naive_utc_now,
        sa_column_kwargs={
            "server_default": text("CURRENT_TIMESTAMP"),
            "onupdate": text("CURRENT_TIMESTAMP"),
        },
    )

    model_config = {"use_enum_values": True}
