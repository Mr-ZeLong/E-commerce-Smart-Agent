"""
测试 chat_utils.py 中的辅助函数
"""

from app.api.v1.chat_utils import create_stream_metadata_message


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
