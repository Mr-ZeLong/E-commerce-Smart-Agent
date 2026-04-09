# app/api/v1/schemas.py
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    # 用户的问题
    question: str = Field(..., json_schema_extra={"example": "内衣拆封了可以退吗？"})

    # 会话 ID，用于后续追踪对话上下文 (v1.0 暂不强制，但预留)
    thread_id: str = Field("default_thread", json_schema_extra={"example": "user_123_session_001"})


class ConfidenceSignalDetail(BaseModel):
    """置信度信号详情"""
    score: float = Field(..., description="信号分数 (0-1)", ge=0, le=1)
    reason: str = Field(..., description="信号评估原因")


class ConfidenceSignals(BaseModel):
    """置信度信号集合"""
    rag: ConfidenceSignalDetail | None = Field(None, description="RAG检索信号")
    llm: ConfidenceSignalDetail | None = Field(None, description="LLM自评估信号")
    emotion: ConfidenceSignalDetail | None = Field(None, description="用户情感信号")


