"""Models for multi-intent decision logging."""

from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class MultiIntentDecisionLog(SQLModel, table=True):
    """Log entry for LLM-assisted multi-intent independence decisions."""

    __tablename__ = "multi_intent_decision_logs"

    id: int | None = Field(default=None, primary_key=True)
    query: str = Field(description="用户原始查询")
    intent_a: str = Field(max_length=32, description="意图A")
    intent_b: str = Field(max_length=32, description="意图B")
    rule_based_result: bool | None = Field(default=None, description="硬编码规则判定结果（若存在）")
    llm_result: bool | None = Field(default=None, description="LLM判定结果")
    llm_reason: str | None = Field(default=None, description="LLM判定理由")
    human_label: bool | None = Field(default=None, description="人工标注结果（用于持续优化）")
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
