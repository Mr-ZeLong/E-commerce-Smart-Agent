from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class ReviewStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ReviewTicket(SQLModel, table=True):
    __tablename__ = "review_tickets"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(index=True, max_length=128)
    user_id: int = Field(foreign_key="users.id", index=True)

    risk_score: float = Field(default=0.0)
    risk_factors: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: str = Field(default=ReviewStatus.PENDING.value, max_length=32)
    assigned_to: int | None = Field(default=None, foreign_key="users.id", index=True)

    sla_deadline: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    resolved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    resolution_action: str | None = Field(default=None, max_length=32)
    resolution_notes: str | None = Field(default=None)
    reviewer_accuracy: float | None = Field(default=None)

    last_messages: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    confidence_score: float | None = Field(default=None)
    transfer_reason: str | None = Field(default=None, max_length=64)


class ReviewerMetrics(SQLModel, table=True):
    __tablename__ = "reviewer_metrics"

    id: int | None = Field(default=None, primary_key=True)
    reviewer_id: int = Field(foreign_key="users.id", index=True)
    period_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    period_end: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    total_tickets: int = Field(default=0)
    avg_handling_time_minutes: float | None = Field(default=None)
    accuracy_score: float | None = Field(default=None)
    sla_compliance_rate: float | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
