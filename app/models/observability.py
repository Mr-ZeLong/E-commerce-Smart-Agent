"""Observability models for graph execution logging."""

from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class GraphExecutionLog(SQLModel, table=True):
    """Log entry for a complete graph execution."""

    __tablename__ = "graph_execution_logs"

    id: int | None = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True, max_length=128)
    user_id: int = Field(foreign_key="users.id", index=True)
    intent_category: str | None = Field(default=None, index=True, max_length=32)
    final_agent: str | None = Field(default=None, max_length=32)
    confidence_score: float | None = None
    needs_human_transfer: bool = False
    query: str | None = Field(default=None, max_length=512, description="User query text")
    langsmith_run_url: str | None = Field(default=None, description="LangSmith trace 链接")
    agent_config_version_id: int | None = Field(
        default=None,
        foreign_key="agent_config_versions.id",
        description="关联的 AgentConfigVersion 快照 ID",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    total_latency_ms: int | None = None
    context_tokens: int | None = None
    context_utilization: float | None = None


class GraphNodeLog(SQLModel, table=True):
    """Log entry for an individual node execution within a graph run."""

    __tablename__ = "graph_node_logs"

    id: int | None = Field(default=None, primary_key=True)
    execution_id: int = Field(foreign_key="graph_execution_logs.id", index=True)
    node_name: str = Field(max_length=32)
    latency_ms: int
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class SupervisorDecision(SQLModel, table=True):
    """Log entry for a supervisor routing decision."""

    __tablename__ = "supervisor_decisions"

    id: int | None = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True, max_length=128)
    primary_intent: str | None = Field(default=None, max_length=32)
    pending_intents: str | None = Field(default=None, max_length=256)
    selected_agents: str | None = Field(default=None, max_length=256)
    execution_mode: str | None = Field(default=None, max_length=16)
    reasoning: str | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
