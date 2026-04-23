"""Online evaluation and quality scoring models."""

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class SentimentEnum(str, Enum):
    """Feedback sentiment."""

    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class ScoreTypeEnum(str, Enum):
    """Quality score type."""

    HELPFULNESS = "helpfulness"
    ACCURACY = "accuracy"
    EMPATHY = "empathy"
    OVERALL = "overall"


class MessageFeedback(SQLModel, table=True):
    """Message feedback table (explicit feedback)."""

    __tablename__ = "message_feedbacks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, description="User ID")
    thread_id: str = Field(index=True, max_length=128, description="Conversation thread ID")
    message_index: int = Field(description="Message index in conversation")

    score: int = Field(description="Score: 1=up, -1=down", ge=-1, le=1)
    comment: str | None = Field(default=None, description="Free text comment")
    category: str | None = Field(default=None, max_length=32, description="Feedback category")
    agent_type: str | None = Field(
        default=None, max_length=32, description="Agent type that generated the response"
    )
    confidence_score: float | None = Field(
        default=None, description="Confidence score at the time of response"
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class QualityScore(SQLModel, table=True):
    """Daily quality score table (aggregated explicit + implicit signals)."""

    __tablename__ = "quality_scores"

    id: int | None = Field(default=None, primary_key=True)
    score_date: date = Field(index=True, description="Score date")
    score_type: str = Field(
        default=ScoreTypeEnum.OVERALL.value, max_length=32, description="Score type"
    )

    total_sessions: int = Field(default=0, description="Total sessions")
    human_transfer_rate: float | None = Field(default=None, description="Human transfer rate")
    avg_confidence: float | None = Field(default=None, description="Average confidence")
    avg_turns: float | None = Field(default=None, description="Average conversation turns")
    implicit_satisfaction_rate: float | None = Field(
        default=None, description="Implicit satisfaction rate"
    )

    explicit_upvotes: int = Field(default=0, description="Upvote count")
    explicit_downvotes: int = Field(default=0, description="Downvote count")

    immediate_transfer_count: int = Field(default=0, description="Immediate human transfer count")
    contradictory_followup_count: int = Field(
        default=0, description="Contradictory follow-up count"
    )
    low_confidence_retry_count: int = Field(default=0, description="Low confidence retry count")

    intent_breakdown: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Intent breakdown data",
    )

    top_degraded_intents: list[str] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Top 3 degraded intents",
    )
    sample_trace_ids: list[str] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Sample trace IDs",
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


class ShadowTestResult(SQLModel, table=True):
    """Shadow testing comparison result stored in database."""

    __tablename__ = "shadow_test_results"

    id: int | None = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True, max_length=128, description="Conversation thread ID")
    user_id: int = Field(foreign_key="users.id", index=True, description="User ID")
    query: str | None = Field(default=None, max_length=512, description="User query")
    production_intent: str | None = Field(default=None, max_length=32)
    shadow_intent: str | None = Field(default=None, max_length=32)
    intent_match: bool = Field(default=False)
    production_answer: str | None = Field(default=None)
    shadow_answer: str | None = Field(default=None)
    jaccard_similarity: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    semantic_similarity: float | None = None
    llm_quality_score: float | None = None
    production_latency_ms: int | None = None
    shadow_latency_ms: int | None = None
    latency_delta_ms: int | None = None
    latency_regression: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class AdversarialTestRun(SQLModel, table=True):
    """Adversarial test suite execution record."""

    __tablename__ = "adversarial_test_runs"

    id: int | None = Field(default=None, primary_key=True)
    run_date: date = Field(index=True, default_factory=date.today)
    total_cases: int = Field(default=0)
    passed_cases: int = Field(default=0)
    failed_cases: int = Field(default=0)
    pass_rate: float = Field(default=0.0)
    category_breakdown: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    severity_breakdown: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    report_markdown: str | None = Field(default=None)
    triggered_by: str = Field(default="scheduled", max_length=32)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
