"""A/B 测试实验模型"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, text
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class ExperimentStatus(str, Enum):
    """实验状态"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class Experiment(SQLModel, table=True):
    """实验表"""

    __tablename__ = "experiments"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=128, description="实验名称")
    description: str | None = Field(default=None, description="实验描述")
    status: str = Field(default=ExperimentStatus.DRAFT.value, max_length=32, description="实验状态")

    # 实验覆盖的维度标记（仅用于快速筛选）
    target_dimensions: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="目标维度JSON",
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


class ExperimentVariant(SQLModel, table=True):
    """实验变体表"""

    __tablename__ = "experiment_variants"

    id: int | None = Field(default=None, primary_key=True)
    experiment_id: int = Field(foreign_key="experiments.id", index=True, description="所属实验 ID")
    name: str = Field(max_length=64, description="变体名称")
    weight: int = Field(default=1, description="流量权重")

    # 变体配置
    system_prompt: str | None = Field(default=None, description="系统提示词版本")
    llm_model: str | None = Field(default=None, max_length=64, description="LLM 模型")
    retriever_top_k: int | None = Field(default=None, description="检索 top-k")
    reranker_enabled: bool | None = Field(default=None, description="是否启用重排序")
    extra_config: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="额外配置",
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


class ExperimentAssignment(SQLModel, table=True):
    """实验用户分配表"""

    __tablename__ = "experiment_assignments"

    id: int | None = Field(default=None, primary_key=True)
    experiment_id: int = Field(foreign_key="experiments.id", index=True, description="实验 ID")
    variant_id: int = Field(foreign_key="experiment_variants.id", index=True, description="变体 ID")
    user_id: int = Field(index=True, description="用户 ID")

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
