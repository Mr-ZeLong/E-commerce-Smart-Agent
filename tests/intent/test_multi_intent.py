"""多意图处理器测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.intent.models import IntentAction, IntentCategory, IntentResult
from app.intent.multi_intent import (
    MultiIntentProcessor,
    MultiIntentResult,
)


class TestMultiIntentResult:
    """测试 MultiIntentResult 数据类"""

    def test_default_initialization(self) -> None:
        """测试默认初始化"""
        result = MultiIntentResult(is_multi_intent=False)
        assert result.is_multi_intent is False
        assert result.sub_intents == []
        assert result.shared_slots == {}
        assert result.execution_order == []

    def test_full_initialization(self) -> None:
        """测试完整初始化"""
        intent_result = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.9,
            slots={"order_id": "123"},
        )
        result = MultiIntentResult(
            is_multi_intent=True,
            sub_intents=[intent_result],
            shared_slots={"order_id": "123"},
            execution_order=[0],
        )
        assert result.is_multi_intent is True
        assert len(result.sub_intents) == 1
        assert result.shared_slots == {"order_id": "123"}
        assert result.execution_order == [0]


class TestMultiIntentProcessorInitialization:
    """测试 MultiIntentProcessor 初始化"""

    def test_init_with_classifier(self) -> None:
        """测试带分类器初始化"""
        mock_classifier = MagicMock()
        processor = MultiIntentProcessor(classifier=mock_classifier)
        assert processor.classifier is mock_classifier
        assert processor.mode == "cascade"

    def test_init_with_single_mode(self) -> None:
        """测试single模式初始化"""
        processor = MultiIntentProcessor(classifier=MagicMock(), mode="single")
        assert processor.mode == "single"

    def test_init_with_cascade_mode(self) -> None:
        """测试cascade模式初始化"""
        processor = MultiIntentProcessor(classifier=MagicMock(), mode="cascade")
        assert processor.mode == "cascade"


class TestMultiIntentProcessorSplitQuery:
    """测试查询拆分功能"""

    def test_single_intent_no_separator(self) -> None:
        """测试单意图无分隔符"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询我的订单")
        assert segments == ["查询我的订单"]

    def test_split_with_separator_bianshun(self) -> None:
        """测试使用'顺便'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单顺便申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_haiyou(self) -> None:
        """测试使用'还有'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单还有申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_lingwai(self) -> None:
        """测试使用'另外'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单另外申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_yiji(self) -> None:
        """测试使用'以及'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单以及申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_he(self) -> None:
        """测试'和'不再作为分隔符（避免正常单意图被误拆分）"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单和申请退款")
        assert segments == ["查询订单和申请退款"]

    def test_split_with_punctuation_comma(self) -> None:
        """测试使用'，然后'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单，然后申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_punctuation_period_lingwai(self) -> None:
        """测试使用'。另外'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单。另外申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_punctuation_period_haiyou(self) -> None:
        """测试使用'。还有'分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单。还有申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_semicolon(self) -> None:
        """测试使用分号分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单;申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_fullwidth_semicolon(self) -> None:
        """测试使用全角分号分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单；申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_multiple_separators(self) -> None:
        """测试多个分隔符"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("查询订单顺便申请退款还有查看物流")
        assert segments == ["查询订单", "申请退款", "查看物流"]

    def test_split_with_whitespace(self) -> None:
        """测试带空白的分隔"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        segments = processor._split_query("  查询订单  顺便  申请退款  ")
        assert segments == ["查询订单", "申请退款"]


class TestMultiIntentProcessorExtractSharedSlots:
    """测试共享槽位提取功能"""

    def test_extract_shared_slots_empty(self) -> None:
        """测试空意图列表"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        shared = processor._extract_shared_slots([])
        assert shared == {}

    def test_extract_shared_slots_single_intent(self) -> None:
        """测试单意图槽位提取"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={"order_id": "123", "user_name": "张三"},
        )
        shared = processor._extract_shared_slots([intent])
        assert shared == {"order_id": "123", "user_name": "张三"}

    def test_extract_shared_slots_multiple_intents(self) -> None:
        """测试多意图槽位合并"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        intent1 = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={"order_id": "123", "user_name": "张三"},
        )
        intent2 = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={"reason": "质量问题", "order_id": "456"},  # order_id 不同
        )
        shared = processor._extract_shared_slots([intent1, intent2])
        # 第一个意图的槽位优先，第二个意图的新槽位被添加
        assert shared == {"order_id": "123", "user_name": "张三", "reason": "质量问题"}

    def test_extract_shared_slots_none_slots(self) -> None:
        """测试槽位为None的情况"""
        processor = MultiIntentProcessor(classifier=MagicMock())
        intent1 = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={},
        )
        intent2 = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={"reason": "质量问题"},
        )
        shared = processor._extract_shared_slots([intent1, intent2])
        assert shared == {"reason": "质量问题"}


class TestMultiIntentProcessorProcess:
    """测试主处理流程"""

    @pytest.mark.asyncio
    async def test_process_single_intent_with_classifier(self) -> None:
        """测试有分类器时单意图处理"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.9,
            slots={"order_id": "123"},
        )

        processor = MultiIntentProcessor(classifier=mock_classifier)
        result = await processor.process("查询订单")

        assert result.is_multi_intent is False
        assert len(result.sub_intents) == 1
        assert result.sub_intents[0].primary_intent == IntentCategory.ORDER
        assert result.shared_slots == {"order_id": "123"}
        assert result.execution_order == [0]
        mock_classifier.classify.assert_called_once_with("查询订单", None)

    @pytest.mark.asyncio
    async def test_process_multi_intent_with_classifier_cascade_mode(self) -> None:
        """测试有分类器时多意图处理（cascade模式）"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = [
            IntentResult(
                primary_intent=IntentCategory.ORDER,
                secondary_intent=IntentAction.QUERY,
                confidence=0.9,
                slots={"order_id": "123"},
            ),
            IntentResult(
                primary_intent=IntentCategory.AFTER_SALES,
                secondary_intent=IntentAction.APPLY,
                confidence=0.85,
                slots={"reason": "质量问题"},
            ),
        ]

        processor = MultiIntentProcessor(classifier=mock_classifier, mode="cascade")
        result = await processor.process("查询订单顺便申请退款")

        assert result.is_multi_intent is True
        assert len(result.sub_intents) == 2
        assert result.sub_intents[0].primary_intent == IntentCategory.ORDER
        assert result.sub_intents[1].primary_intent == IntentCategory.AFTER_SALES
        assert result.shared_slots == {"order_id": "123", "reason": "质量问题"}
        # 按置信度降序：ORDER (0.9) 在 AFTER_SALES (0.85) 之前
        assert result.execution_order == [0, 1]
        assert mock_classifier.classify.call_count == 2

    @pytest.mark.asyncio
    async def test_process_multi_intent_single_mode(self) -> None:
        """测试single模式只返回置信度最高的意图"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = [
            IntentResult(
                primary_intent=IntentCategory.ORDER,
                secondary_intent=IntentAction.QUERY,
                confidence=0.7,
                slots={"order_id": "123"},
            ),
            IntentResult(
                primary_intent=IntentCategory.AFTER_SALES,
                secondary_intent=IntentAction.APPLY,
                confidence=0.9,
                slots={"reason": "质量问题"},
            ),
        ]

        processor = MultiIntentProcessor(classifier=mock_classifier, mode="single")
        result = await processor.process("查询订单顺便申请退款")

        assert result.is_multi_intent is True
        assert len(result.sub_intents) == 1
        # 应该返回置信度最高的 AFTER_SALES
        assert result.sub_intents[0].primary_intent == IntentCategory.AFTER_SALES
        assert result.sub_intents[0].confidence == 0.9
        assert result.execution_order == [0]

    @pytest.mark.asyncio
    async def test_process_multi_intent_max_limit(self) -> None:
        """测试最多2个意图限制"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = [
            IntentResult(
                primary_intent=IntentCategory.ORDER,
                secondary_intent=IntentAction.QUERY,
                confidence=0.9,
                slots={},
            ),
            IntentResult(
                primary_intent=IntentCategory.AFTER_SALES,
                secondary_intent=IntentAction.APPLY,
                confidence=0.85,
                slots={},
            ),
        ]

        processor = MultiIntentProcessor(classifier=mock_classifier)
        # 3个意图，但只处理前2个
        result = await processor.process("查询订单顺便申请退款还有查看物流")

        assert result.is_multi_intent is True
        assert len(result.sub_intents) == 2
        assert mock_classifier.classify.call_count == 2

    @pytest.mark.asyncio
    async def test_process_with_conversation_history(self) -> None:
        """测试带对话历史的处理"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.9,
            slots={},
        )

        processor = MultiIntentProcessor(classifier=mock_classifier)
        history = [{"role": "user", "content": "之前的对话"}]
        result = await processor.process("查询订单", conversation_history=history)

        # 验证结果被正确使用
        assert result.is_multi_intent is False
        assert len(result.sub_intents) == 1
        assert result.sub_intents[0].primary_intent == IntentCategory.ORDER

        # 验证分类器被调用时history被转换为context dict
        mock_classifier.classify.assert_called_once_with("查询订单", {"history": history})

    @pytest.mark.asyncio
    async def test_process_classifier_exception_single_intent(self) -> None:
        """测试单意图时分类器异常直接抛出"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = ValueError("分类器错误")

        processor = MultiIntentProcessor(classifier=mock_classifier)
        with pytest.raises(ValueError, match="分类器错误"):
            await processor.process("查询订单")

    @pytest.mark.asyncio
    async def test_process_classifier_exception_multi_intent(self) -> None:
        """测试多意图时分类器异常直接抛出"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = ValueError("分类器错误")

        processor = MultiIntentProcessor(classifier=mock_classifier)
        with pytest.raises(ValueError, match="分类器错误"):
            await processor.process("查询订单顺便申请退款")

    @pytest.mark.asyncio
    async def test_process_classifier_partial_exception(self) -> None:
        """测试部分segment分类异常时直接抛出"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = [
            IntentResult(
                primary_intent=IntentCategory.ORDER,
                secondary_intent=IntentAction.QUERY,
                confidence=0.9,
                slots={"order_id": "123"},
            ),
            ValueError("第二个segment失败"),
        ]

        processor = MultiIntentProcessor(classifier=mock_classifier)
        with pytest.raises(ValueError, match="第二个segment失败"):
            await processor.process("查询订单顺便申请退款")
