"""投诉工单模型"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class ComplaintCategory(str, Enum):
    """投诉类别"""

    PRODUCT_DEFECT = "product_defect"
    SERVICE = "service"
    LOGISTICS = "logistics"
    OTHER = "other"


class ComplaintStatus(str, Enum):
    """投诉状态"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ComplaintUrgency(str, Enum):
    """投诉紧急程度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExpectedResolution(str, Enum):
    """期望解决方案"""

    REFUND = "refund"
    EXCHANGE = "exchange"
    APOLOGY = "apology"
    COMPENSATION = "compensation"


class ComplaintTicket(SQLModel, table=True):
    """投诉工单表"""

    __tablename__ = "complaint_tickets"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, description="用户 ID")
    thread_id: str = Field(index=True, max_length=128, description="会话线程 ID")

    category: str = Field(max_length=32, description="投诉类别")
    order_sn: str | None = Field(default=None, max_length=64, description="关联订单号")
    description: str = Field(description="详细描述")
    expected_resolution: str = Field(max_length=32, description="期望解决方案")

    status: str = Field(default=ComplaintStatus.OPEN.value, max_length=32, description="工单状态")
    urgency: str = Field(
        default=ComplaintUrgency.MEDIUM.value, max_length=32, description="紧急程度"
    )
    assigned_to: int | None = Field(default=None, index=True, description="分配给的管理员 ID")

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
