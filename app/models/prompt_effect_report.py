"""Models for prompt engineering effect reports."""

from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class PromptEffectReport(SQLModel, table=True):
    """Monthly prompt engineering effect report."""

    __tablename__ = "prompt_effect_reports"

    id: int | None = Field(default=None, primary_key=True)
    report_month: str = Field(max_length=7, description="报告月份 (YYYY-MM)")
    agent_name: str = Field(max_length=32, description="Agent 名称")
    version_id: int | None = Field(
        default=None,
        foreign_key="agent_config_versions.id",
        description="关联的版本 ID",
    )
    total_sessions: int = Field(default=0, description="总会话数")
    avg_confidence: float | None = None
    transfer_rate: float | None = None
    avg_latency_ms: float | None = None
    key_changes: str | None = Field(default=None, description="本月关键变更摘要")
    recommendation: str | None = Field(default=None, description="优化建议")

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
