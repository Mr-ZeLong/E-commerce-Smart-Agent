# app/api/v1/chat_utils.py
"""
v4.1 新增：聊天 API 工具函数
用于生成置信度卡片和转人工卡片内容
"""

from typing import Any

# ========== 置信度阈值常量 ==========
HIGH_CONFIDENCE_THRESHOLD = 0.8
MEDIUM_CONFIDENCE_THRESHOLD = 0.6


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
    score = max(0.0, min(1.0, score))

    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    elif score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    else:
        return "low"


def create_confidence_message(
    confidence_score: float,
    confidence_signals: dict[str, Any] | None,
    needs_human_transfer: bool = False,
    transfer_reason: str | None = None,
) -> dict[str, Any]:
    """
    创建置信度信息卡片内容

    Args:
        confidence_score: 置信度分数 (0-1)
        confidence_signals: 信号详情，包含 rag、llm、emotion 等信号
        needs_human_transfer: 是否需要转人工
        transfer_reason: 转人工原因

    Returns:
        置信度卡片内容字典
    """
    # 确保分数在有效范围内
    confidence_score = max(0.0, min(1.0, confidence_score))

    # 确定置信度等级
    confidence_level = get_confidence_level(confidence_score)

    # 构建信号详情
    signals = {}
    if confidence_signals:
        for signal_name in ["rag", "llm", "emotion"]:
            if signal_name in confidence_signals:
                signal_data = confidence_signals[signal_name]
                signals[signal_name] = {
                    "score": signal_data.get("score", 0.0),
                    "reason": signal_data.get("reason", "未知"),
                }
    else:
        # 如果没有信号详情，使用默认值
        signals = {
            "rag": {"score": confidence_score, "reason": "综合评估"},
            "llm": {"score": confidence_score, "reason": "综合评估"},
            "emotion": {"score": 0.7, "reason": "无明显情绪"},
        }

    return {
        "card_type": "confidence_info",
        "confidence_score": round(confidence_score, 2),
        "confidence_level": confidence_level,
        "signals": signals,
        "needs_human_transfer": needs_human_transfer,
        "transfer_reason": transfer_reason,
    }


def create_transfer_message(
    confidence_score: float,
    transfer_reason: str,
    transfer_message: str | None = None,
    estimated_wait_time: str = "约 2 分钟",
    extra_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    创建转人工信息卡片内容

    Args:
        confidence_score: 置信度分数 (0-1)
        transfer_reason: 转人工原因代码
        transfer_message: 转人工提示消息
        estimated_wait_time: 预计等待时间
        extra_info: 额外信息

    Returns:
        转人工卡片内容字典
    """
    # 确保分数在有效范围内
    confidence_score = max(0.0, min(1.0, confidence_score))

    # 确定置信度等级
    confidence_level = get_confidence_level(confidence_score)

    # 默认转人工消息
    if transfer_message is None:
        transfer_message = "系统置信度不足，已为您转接人工客服"

    return {
        "card_type": "human_transfer",
        "confidence_score": round(confidence_score, 2),
        "confidence_level": confidence_level,
        "transfer_reason": transfer_reason,
        "transfer_reason_text": TRANSFER_REASON_MAP.get(transfer_reason, transfer_reason),
        "transfer_message": transfer_message,
        "estimated_wait_time": estimated_wait_time,
        "extra_info": extra_info or {},
    }


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
        confidence_score = max(0.0, min(1.0, confidence_score))
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
