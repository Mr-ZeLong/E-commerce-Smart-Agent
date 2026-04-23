from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class TokenUsageLog(SQLModel, table=True):
    __tablename__ = "token_usage_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    thread_id: str = Field(index=True, max_length=128)
    agent_type: str = Field(max_length=32)

    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)

    query_text: str | None = Field(default=None, max_length=512)
    model_name: str | None = Field(default=None, max_length=64)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class OptimizationSuggestionStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class OptimizationSuggestion(SQLModel, table=True):
    __tablename__ = "optimization_suggestions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    thread_id: str | None = Field(default=None, index=True, max_length=128)

    suggestion_type: str = Field(max_length=32)
    message: str = Field()
    context_data: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    status: str = Field(default=OptimizationSuggestionStatus.PENDING.value, max_length=32)

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
