"""
测试 chat_utils.py 中的辅助函数
"""

import pytest

from app.api.v1.chat_utils import (
    create_confidence_message,
    create_stream_metadata_message,
    create_transfer_message,
)


class TestCreateConfidenceMessage:
    """测试 create_confidence_message 函数"""

    def test_high_confidence(self):
        """测试高置信度情况"""
        signals = {
            "rag": {"score": 0.9, "reason": "检索质量良好"},
            "llm": {"score": 0.85, "reason": "回答完整"},
            "emotion": {"score": 0.8, "reason": "情绪稳定"},
        }
        result = create_confidence_message(
            confidence_score=0.85,
            confidence_signals=signals,
            needs_human_transfer=False,
            transfer_reason=None,
        )

        assert result["card_type"] == "confidence_info"
        assert result["confidence_score"] == 0.85
        assert result["confidence_level"] == "high"
        assert result["needs_human_transfer"] is False
        assert result["transfer_reason"] is None
        assert "rag" in result["signals"]
        assert "llm" in result["signals"]
        assert "emotion" in result["signals"]

    def test_medium_confidence(self):
        """测试中置信度情况"""
        signals = {
            "rag": {"score": 0.7, "reason": "检索质量一般"},
            "llm": {"score": 0.65, "reason": "回答较完整"},
            "emotion": {"score": 0.6, "reason": "情绪中性"},
        }
        result = create_confidence_message(
            confidence_score=0.65,
            confidence_signals=signals,
            needs_human_transfer=False,
            transfer_reason=None,
        )

        assert result["confidence_level"] == "medium"
        assert result["needs_human_transfer"] is False

    def test_low_confidence_with_transfer(self):
        """测试低置信度需要转人工的情况"""
        signals = {
            "rag": {"score": 0.4, "reason": "检索质量差"},
            "llm": {"score": 0.35, "reason": "回答不完整"},
            "emotion": {"score": 0.5, "reason": "情绪中性"},
        }
        result = create_confidence_message(
            confidence_score=0.45,
            confidence_signals=signals,
            needs_human_transfer=True,
            transfer_reason="confidence_low",
        )

        assert result["confidence_level"] == "low"
        assert result["needs_human_transfer"] is True
        assert result["transfer_reason"] == "confidence_low"

    def test_empty_signals(self):
        """测试信号为空的情况"""
        result = create_confidence_message(
            confidence_score=0.7,
            confidence_signals=None,
            needs_human_transfer=False,
            transfer_reason=None,
        )

        assert result["confidence_score"] == 0.7
        assert "rag" in result["signals"]
        assert "llm" in result["signals"]
        assert "emotion" in result["signals"]

    def test_partial_signals(self):
        """测试部分信号缺失的情况"""
        signals = {
            "rag": {"score": 0.8, "reason": "检索质量良好"},
        }
        result = create_confidence_message(
            confidence_score=0.75,
            confidence_signals=signals,
        )

        assert "rag" in result["signals"]
        assert "llm" not in result["signals"]
        assert "emotion" not in result["signals"]


class TestCreateTransferMessage:
    """测试 create_transfer_message 函数"""

    def test_basic_transfer(self):
        """测试基本转人工消息"""
        result = create_transfer_message(
            confidence_score=0.45,
            transfer_reason="confidence_low",
        )

        assert result["card_type"] == "human_transfer"
        assert result["confidence_score"] == 0.45
        assert result["confidence_level"] == "low"
        assert result["transfer_reason"] == "confidence_low"
        assert result["transfer_reason_text"] == "置信度不足"
        assert "已为您转接人工客服" in result["transfer_message"]
        assert result["estimated_wait_time"] == "约 2 分钟"

    def test_custom_message(self):
        """测试自定义转人工消息"""
        result = create_transfer_message(
            confidence_score=0.3,
            transfer_reason="system_error",
            transfer_message="系统出现错误，正在为您转接人工客服",
            estimated_wait_time="约 5 分钟",
        )

        assert result["transfer_reason_text"] == "系统错误"
        assert result["transfer_message"] == "系统出现错误，正在为您转接人工客服"
        assert result["estimated_wait_time"] == "约 5 分钟"

    def test_all_reason_types(self):
        """测试所有转人工原因类型"""
        reason_map = {
            "confidence_low": "置信度不足",
            "system_error": "系统错误",
            "user_request": "用户要求",
            "risk_detected": "检测到风险",
            "complex_issue": "问题过于复杂",
        }

        for reason_code, expected_text in reason_map.items():
            result = create_transfer_message(
                confidence_score=0.4,
                transfer_reason=reason_code,
            )
            assert result["transfer_reason_text"] == expected_text

    def test_unknown_reason(self):
        """测试未知的转人工原因"""
        result = create_transfer_message(
            confidence_score=0.4,
            transfer_reason="unknown_reason",
        )

        assert result["transfer_reason_text"] == "unknown_reason"

    def test_with_extra_info(self):
        """测试带额外信息的情况"""
        extra = {"queue_position": 3, "agent_name": "客服小王"}
        result = create_transfer_message(
            confidence_score=0.5,
            transfer_reason="confidence_low",
            extra_info=extra,
        )

        assert result["extra_info"] == extra


class TestCreateStreamMetadataMessage:
    """测试 create_stream_metadata_message 函数"""

    def test_full_metadata(self):
        """测试完整的元数据消息"""
        signals = {
            "rag": {"score": 0.8, "reason": "检索质量良好"},
            "llm": {"score": 0.7, "reason": "回答完整"},
        }
        result = create_stream_metadata_message(
            confidence_score=0.75,
            confidence_signals=signals,
            needs_human_transfer=False,
            transfer_reason=None,
            audit_level="auto",
        )

        assert result["type"] == "metadata"
        assert result["confidence_score"] == 0.75
        assert result["confidence_level"] == "medium"
        assert result["confidence_signals"] == signals
        assert result["needs_human_transfer"] is False
        # transfer_reason is None, so it should not be included in the result
        assert "transfer_reason" not in result
        assert result["audit_level"] == "auto"

    def test_high_confidence_level(self):
        """测试高置信度等级判定"""
        result = create_stream_metadata_message(confidence_score=0.85)
        assert result["confidence_level"] == "high"

    def test_low_confidence_level(self):
        """测试低置信度等级判定"""
        result = create_stream_metadata_message(confidence_score=0.45)
        assert result["confidence_level"] == "low"

    def test_partial_metadata(self):
        """测试部分元数据"""
        result = create_stream_metadata_message(
            confidence_score=0.7,
            audit_level="none",
        )

        assert result["type"] == "metadata"
        assert result["confidence_score"] == 0.7
        assert result["confidence_level"] == "medium"
        assert result["audit_level"] == "none"
        assert "needs_human_transfer" not in result
        assert "transfer_reason" not in result

    def test_empty_metadata(self):
        """测试空元数据"""
        result = create_stream_metadata_message()

        assert result == {"type": "metadata"}

    def test_with_transfer_info(self):
        """测试包含转人工信息的元数据"""
        result = create_stream_metadata_message(
            confidence_score=0.4,
            needs_human_transfer=True,
            transfer_reason="confidence_low",
            audit_level="manual",
        )

        assert result["needs_human_transfer"] is True
        assert result["transfer_reason"] == "confidence_low"
        assert result["audit_level"] == "manual"
