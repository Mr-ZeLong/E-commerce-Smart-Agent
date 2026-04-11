# app/api/v1/chat_utils.py
"""
v4.1 新增：聊天 API 工具函数
用于生成置信度卡片和转人工卡片内容
"""

from typing import Any

from app.core.config import settings
from app.core.utils import clamp_score


# ========== 转人工原因常量 ==========
class TransferReason:
    """转人工原因代码"""

    CONFIDENCE_LOW = "confidence_low"
    SYSTEM_ERROR = "system_error"
    USER_REQUEST = "user_request"
    RISK_DETECTED = "risk_detected"
    COMPLEX_ISSUE = "complex_issue"


# ========== 转人工原因映射 ==========
TRANSFER_REASON_MAP: dict[str, str] = {
    TransferReason.CONFIDENCE_LOW: "置信度不足",
    TransferReason.SYSTEM_ERROR: "系统错误",
    TransferReason.USER_REQUEST: "用户要求",
    TransferReason.RISK_DETECTED: "检测到风险",
    TransferReason.COMPLEX_ISSUE: "问题过于复杂",
}


def get_confidence_level(score: float) -> str:
    """
    根据置信度分数确定置信度等级

    Args:
        score: 置信度分数 (0-1)

    Returns:
        置信度等级: "high" | "medium" | "low"
    """
    # 确保分数在有效范围内
    score = clamp_score(score)

    if score >= settings.CONFIDENCE.HIGH_THRESHOLD:
        return "high"
    elif score >= settings.CONFIDENCE.MEDIUM_THRESHOLD:
        return "medium"
    else:
        return "low"


def create_stream_metadata_message(
    confidence_score: float | None = None,
    confidence_signals: dict[str, Any] | None = None,
    needs_human_transfer: bool | None = None,
    transfer_reason: str | None = None,
    audit_level: str | None = None,
) -> dict[str, Any]:
    """
    创建流式响应的元数据消息

    在 SSE 流结束时发送，包含置信度等元数据

    Args:
        confidence_score: 置信度分数
        confidence_signals: 信号详情
        needs_human_transfer: 是否需要转人工
        transfer_reason: 转人工原因
        audit_level: 审核级别

    Returns:
        元数据消息字典
    """
    metadata: dict[str, Any] = {
        "type": "metadata",
    }

    if confidence_score is not None:
        # 确保分数在有效范围内
        confidence_score = clamp_score(confidence_score)
        metadata["confidence_score"] = round(confidence_score, 2)
        metadata["confidence_level"] = get_confidence_level(confidence_score)

    if confidence_signals:
        metadata["confidence_signals"] = confidence_signals

    if needs_human_transfer is not None:
        metadata["needs_human_transfer"] = needs_human_transfer

    if transfer_reason:
        metadata["transfer_reason"] = transfer_reason

    if audit_level:
        metadata["audit_level"] = audit_level

    return metadata
