"""在线评估与质量评分模型"""

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class SentimentEnum(str, Enum):
    """反馈情感"""

    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class ScoreTypeEnum(str, Enum):
    """质量评分类型"""

    HELPFULNESS = "helpfulness"
    ACCURACY = "accuracy"
    EMPATHY = "empathy"
    OVERALL = "overall"


class MessageFeedback(SQLModel, table=True):
    """消息反馈表（显式反馈）"""

    __tablename__ = "message_feedbacks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, description="用户 ID")
    thread_id: str = Field(index=True, max_length=128, description="会话线程 ID")
    message_index: int = Field(description="消息在会话中的索引")

    score: int = Field(description="评分：1=up, -1=down", ge=-1, le=1)
    comment: str | None = Field(default=None, description="自由文本评论")

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class QualityScore(SQLModel, table=True):
    """每日质量评分表（聚合显式+隐式信号）"""

    __tablename__ = "quality_scores"

    id: int | None = Field(default=None, primary_key=True)
    score_date: date = Field(index=True, description="评分日期")
    score_type: str = Field(
        default=ScoreTypeEnum.OVERALL.value, max_length=32, description="评分类型"
    )

    # 整体指标
    total_sessions: int = Field(default=0, description="总会话数")
    human_transfer_rate: float | None = Field(default=None, description="人工转接率")
    avg_confidence: float | None = Field(default=None, description="平均置信度")
    avg_turns: float | None = Field(default=None, description="平均对话轮数")
    implicit_satisfaction_rate: float | None = Field(default=None, description="隐式满意率")

    # 显式反馈
    explicit_upvotes: int = Field(default=0, description="点赞数")
    explicit_downvotes: int = Field(default=0, description="点踩数")

    # 隐式负向信号
    immediate_transfer_count: int = Field(default=0, description="立即转人工数")
    contradictory_followup_count: int = Field(default=0, description="矛盾追问数")
    low_confidence_retry_count: int = Field(default=0, description="低置信重试数")

    # 按意图细分（JSON: intent -> metrics）
    intent_breakdown: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="意图细分数据",
    )

    # Top 3 劣化意图及样本 trace IDs
    top_degraded_intents: list[str] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Top 3 劣化意图",
    )
    sample_trace_ids: list[str] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="样本 trace IDs",
    )

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
