# app/api/v1/schemas.py
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    # 用户的问题
    question: str = Field(..., json_schema_extra={"example": "内衣拆封了可以退吗？"})

    # 会话 ID，用于后续追踪对话上下文 (v1.0 暂不强制，但预留)
    thread_id: str = Field("default_thread", json_schema_extra={"example": "user_123_session_001"})


class ChatResponse(BaseModel):
    # 非流式模式下的返回结构
    answer: str


class ConfidenceSignalDetail(BaseModel):
    """置信度信号详情"""
    score: float = Field(..., description="信号分数 (0-1)", ge=0, le=1)
    reason: str = Field(..., description="信号评估原因")


class ConfidenceSignals(BaseModel):
    """置信度信号集合"""
    rag: ConfidenceSignalDetail | None = Field(None, description="RAG检索信号")
    llm: ConfidenceSignalDetail | None = Field(None, description="LLM自评估信号")
    emotion: ConfidenceSignalDetail | None = Field(None, description="用户情感信号")


class ChatResponseMetadata(BaseModel):
    """
    v4.1 新增：聊天响应元数据

    包含置信度分数、信号详情、审核状态等信息
    用于流式响应结束时发送的元数据消息
    """
    confidence_score: float | None = Field(
        None,
        description="综合置信度分数 (0-1)",
        ge=0,
        le=1,
        json_schema_extra={"example": 0.75}
    )
    confidence_level: str | None = Field(
        None,
        description="置信度等级: high | medium | low",
        json_schema_extra={"example": "medium"}
    )
    confidence_signals: ConfidenceSignals | None = Field(
        None,
        description="各信号详情"
    )
    needs_human_transfer: bool = Field(
        False,
        description="是否需要转人工"
    )
    transfer_reason: str | None = Field(
        None,
        description="转人工原因代码",
        json_schema_extra={"example": "confidence_low"}
    )
    audit_level: str | None = Field(
        None,
        description="审核级别: none | auto | manual",
        json_schema_extra={"example": "auto"}
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confidence_score": 0.75,
                "confidence_level": "medium",
                "confidence_signals": {
                    "rag": {"score": 0.8, "reason": "检索质量良好"},
                    "llm": {"score": 0.7, "reason": "回答完整"},
                    "emotion": {"score": 0.75, "reason": "无明显情绪"}
                },
                "needs_human_transfer": False,
                "transfer_reason": None,
                "audit_level": "auto"
            }
        }
    )


class ConfidenceCardContent(BaseModel):
    """
    v4.1 新增：置信度卡片内容

    用于前端展示置信度评估结果
    """
    card_type: str = Field("confidence_info", description="卡片类型")
    confidence_score: float = Field(..., description="置信度分数", ge=0, le=1)
    confidence_level: str = Field(..., description="置信度等级: high | medium | low")
    signals: dict[str, Any] = Field(..., description="信号详情")
    needs_human_transfer: bool = Field(..., description="是否需要转人工")
    transfer_reason: str | None = Field(None, description="转人工原因")


class TransferCardContent(BaseModel):
    """
    v4.1 新增：转人工卡片内容

    用于前端展示转人工信息
    """
    card_type: str = Field("human_transfer", description="卡片类型")
    confidence_score: float = Field(..., description="置信度分数", ge=0, le=1)
    confidence_level: str = Field(..., description="置信度等级: high | medium | low")
    transfer_reason: str = Field(..., description="转人工原因代码")
    transfer_reason_text: str = Field(..., description="转人工原因文本")
    transfer_message: str = Field(..., description="转人工提示消息")
    estimated_wait_time: str = Field("约 2 分钟", description="预计等待时间")
    extra_info: dict[str, Any] | None = Field(None, description="额外信息")
