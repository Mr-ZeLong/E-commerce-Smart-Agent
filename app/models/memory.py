from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class UserProfile(SQLModel, table=True):
    """用户画像表"""

    __tablename__ = "user_profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, description="用户 ID")
    membership_level: str = Field(max_length=32, description="会员等级")
    preferred_language: str = Field(default="zh", max_length=10, description="偏好语言")
    timezone: str = Field(default="Asia/Shanghai", max_length=50, description="时区")
    total_orders: int = Field(default=0, description="总订单数")
    lifetime_value: float = Field(default=0.0, description="生命周期价值")

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


class UserPreference(SQLModel, table=True):
    """用户偏好表"""

    __tablename__ = "user_preferences"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, description="用户 ID")
    preference_key: str = Field(max_length=64, description="偏好键")
    preference_value: str = Field(description="偏好值")

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


class InteractionSummary(SQLModel, table=True):
    """对话摘要表"""

    __tablename__ = "interaction_summaries"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, description="用户 ID")
    thread_id: str = Field(index=True, max_length=128, description="会话线程 ID")
    summary_text: str = Field(description="摘要文本")
    resolved_intent: str = Field(max_length=32, description="已解决意图")
    satisfaction_score: float | None = Field(default=None, description="满意度评分")

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


class UserFact(SQLModel, table=True):
    """用户事实表"""

    __tablename__ = "user_facts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, description="用户 ID")
    fact_type: str = Field(max_length=32, description="事实类型")
    content: str = Field(description="内容")
    confidence: float = Field(default=0.0, description="置信度")
    source_thread_id: str | None = Field(
        default=None, max_length=128, description="来源会话线程 ID"
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


class AgentConfig(SQLModel, table=True):
    """Agent 配置表"""

    __tablename__ = "agent_configs"

    id: int | None = Field(default=None, primary_key=True)
    agent_name: str = Field(unique=True, index=True, max_length=32, description="Agent 名称")
    system_prompt: str | None = Field(default=None, description="系统提示词")
    previous_system_prompt: str | None = Field(
        default=None, description="上一次系统提示词，用于回滚"
    )
    confidence_threshold: float = Field(default=0.7, description="置信度阈值")
    max_retries: int = Field(default=3, description="最大重试次数")
    enabled: bool = Field(default=True, description="是否启用")

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )


class RoutingRule(SQLModel, table=True):
    """路由规则表"""

    __tablename__ = "routing_rules"

    id: int | None = Field(default=None, primary_key=True)
    intent_category: str = Field(index=True, max_length=32, description="意图类别")
    target_agent: str = Field(max_length=32, description="目标 Agent")
    priority: int = Field(default=0, description="优先级")
    condition_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="条件 JSON",
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


class AgentConfigAuditLog(SQLModel, table=True):
    """Agent 配置变更审计日志表"""

    __tablename__ = "agent_config_audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    agent_name: str = Field(index=True, max_length=32, description="Agent 名称")
    changed_by: int = Field(description="管理员用户 ID")
    field_name: str = Field(max_length=64, description="变更字段")
    old_value: str | None = Field(default=None, description="旧值")
    new_value: str | None = Field(default=None, description="新值")

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
