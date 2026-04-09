"""多意图处理器测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.intent.models import IntentAction, IntentCategory, IntentResult
from app.intent.multi_intent import (
    IntentClassifierProtocol,
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

    def test_init_without_classifier(self) -> None:
        """测试无分类器初始化"""
        processor = MultiIntentProcessor()
        assert processor.classifier is None
        assert processor.mode == "cascade"
        assert processor.MAX_INTENTS == 2
        assert len(processor.INTENT_SEPARATORS) > 0

    def test_init_with_classifier(self) -> None:
        """测试带分类器初始化"""
        mock_classifier = MagicMock()
        processor = MultiIntentProcessor(classifier=mock_classifier)
        assert processor.classifier is mock_classifier
        assert processor.mode == "cascade"

    def test_init_with_single_mode(self) -> None:
        """测试single模式初始化"""
        processor = MultiIntentProcessor(mode="single")
        assert processor.mode == "single"

    def test_init_with_cascade_mode(self) -> None:
        """测试cascade模式初始化"""
        processor = MultiIntentProcessor(mode="cascade")
        assert processor.mode == "cascade"

    def test_init_with_invalid_mode(self) -> None:
        """测试无效模式初始化应抛出ValueError"""
        with pytest.raises(ValueError, match="Invalid mode"):
            MultiIntentProcessor(mode="invalid")


class TestMultiIntentProcessorSplitQuery:
    """测试查询拆分功能"""

    def test_single_intent_no_separator(self) -> None:
        """测试单意图无分隔符"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询我的订单")
        assert segments == ["查询我的订单"]

    def test_split_with_separator_bianshun(self) -> None:
        """测试使用'顺便'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单顺便申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_haiyou(self) -> None:
        """测试使用'还有'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单还有申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_lingwai(self) -> None:
        """测试使用'另外'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单另外申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_yiji(self) -> None:
        """测试使用'以及'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单以及申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_separator_he(self) -> None:
        """测试使用'和'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单和申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_punctuation_comma(self) -> None:
        """测试使用'，然后'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单，然后申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_punctuation_period_lingwai(self) -> None:
        """测试使用'。另外'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单。另外申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_punctuation_period_haiyou(self) -> None:
        """测试使用'。还有'分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单。还有申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_semicolon(self) -> None:
        """测试使用分号分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单;申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_with_fullwidth_semicolon(self) -> None:
        """测试使用全角分号分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单；申请退款")
        assert segments == ["查询订单", "申请退款"]

    def test_split_multiple_separators(self) -> None:
        """测试多个分隔符"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("查询订单顺便申请退款还有查看物流")
        assert segments == ["查询订单", "申请退款", "查看物流"]

    def test_split_with_whitespace(self) -> None:
        """测试带空白的分隔"""
        processor = MultiIntentProcessor()
        segments = processor._split_query("  查询订单  顺便  申请退款  ")
        assert segments == ["查询订单", "申请退款"]


class TestMultiIntentProcessorExtractSharedSlots:
    """测试共享槽位提取功能"""

    def test_extract_shared_slots_empty(self) -> None:
        """测试空意图列表"""
        processor = MultiIntentProcessor()
        shared = processor._extract_shared_slots([])
        assert shared == {}

    def test_extract_shared_slots_single_intent(self) -> None:
        """测试单意图槽位提取"""
        processor = MultiIntentProcessor()
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={"order_id": "123", "user_name": "张三"},
        )
        shared = processor._extract_shared_slots([intent])
        assert shared == {"order_id": "123", "user_name": "张三"}

    def test_extract_shared_slots_multiple_intents(self) -> None:
        """测试多意图槽位合并"""
        processor = MultiIntentProcessor()
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
        processor = MultiIntentProcessor()
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


class TestMultiIntentProcessorDetermineExecutionOrder:
    """测试执行顺序确定功能"""

    def test_determine_order_empty(self) -> None:
        """测试空意图列表"""
        processor = MultiIntentProcessor()
        order = processor._determine_execution_order([])
        assert order == []

    def test_determine_order_single(self) -> None:
        """测试单意图顺序"""
        processor = MultiIntentProcessor()
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.9,
        )
        order = processor._determine_execution_order([intent])
        assert order == [0]

    def test_determine_order_multiple_by_confidence(self) -> None:
        """测试多意图按置信度降序排序"""
        processor = MultiIntentProcessor()
        intent1 = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.7,
        )
        intent2 = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            confidence=0.9,
        )
        order = processor._determine_execution_order([intent1, intent2])
        # 按置信度降序：intent2 (0.9) 应该在 intent1 (0.7) 之前
        assert order == [1, 0]

    def test_determine_order_with_zero_confidence(self) -> None:
        """测试包含零置信度的排序"""
        processor = MultiIntentProcessor()
        intent1 = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.0,
        )
        intent2 = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            confidence=0.5,
        )
        order = processor._determine_execution_order([intent1, intent2])
        assert order == [1, 0]


class TestMultiIntentProcessorApplySharedSlots:
    """测试共享槽位应用功能"""

    def test_apply_shared_slots_empty(self) -> None:
        """测试应用到空意图列表"""
        processor = MultiIntentProcessor()
        result = processor.apply_shared_slots([], {"shared": "value"})
        assert result == []

    def test_apply_shared_slots_to_single(self) -> None:
        """测试应用到单意图"""
        processor = MultiIntentProcessor()
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={"order_id": "123"},
        )
        result = processor.apply_shared_slots([intent], {"user_name": "张三"})
        assert len(result) == 1
        assert result[0].slots == {"user_name": "张三", "order_id": "123"}

    def test_apply_shared_slots_merge(self) -> None:
        """测试槽位合并（意图槽位优先）"""
        processor = MultiIntentProcessor()
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={"order_id": "123"},  # 意图自己的槽位
        )
        result = processor.apply_shared_slots([intent], {"order_id": "999", "user_name": "张三"})
        # 意图自己的槽位优先于共享槽位
        assert result[0].slots == {"order_id": "123", "user_name": "张三"}

    def test_apply_shared_slots_no_existing_slots(self) -> None:
        """测试意图没有现有槽位"""
        processor = MultiIntentProcessor()
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={},
        )
        result = processor.apply_shared_slots([intent], {"user_name": "张三"})
        assert result[0].slots == {"user_name": "张三"}

    def test_apply_shared_slots_preserves_other_fields(self) -> None:
        """测试保留其他字段"""
        processor = MultiIntentProcessor()
        intent = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            tertiary_intent="ORDER_TRACKING",
            confidence=0.9,
            slots={"order_id": "123"},
            missing_slots=["user_name"],
            needs_clarification=True,
            clarification_question="请问订单号是多少？",
            raw_query="查询订单",
        )
        result = processor.apply_shared_slots([intent], {"shared": "value"})
        assert result[0].primary_intent == IntentCategory.ORDER
        assert result[0].secondary_intent == IntentAction.QUERY
        assert result[0].tertiary_intent == "ORDER_TRACKING"
        assert result[0].confidence == 0.9
        assert result[0].missing_slots == ["user_name"]
        assert result[0].needs_clarification is True
        assert result[0].clarification_question == "请问订单号是多少？"
        assert result[0].raw_query == "查询订单"


class TestMultiIntentProcessorProcess:
    """测试主处理流程"""

    @pytest.mark.asyncio
    async def test_process_single_intent_without_classifier(self) -> None:
        """测试无分类器时单意图处理"""
        processor = MultiIntentProcessor()
        result = await processor.process("查询订单")
        assert result.is_multi_intent is False
        assert result.sub_intents == []
        assert result.shared_slots == {}

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
        mock_classifier.classify.assert_called_once_with(
            "查询订单", {"history": history}
        )

    @pytest.mark.asyncio
    async def test_process_classifier_returns_none(self) -> None:
        """测试分类器返回None的情况"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = None

        processor = MultiIntentProcessor(classifier=mock_classifier)
        result = await processor.process("查询订单顺便申请退款")

        assert result.is_multi_intent is True
        assert result.sub_intents == []  # None被过滤
        assert result.shared_slots == {}

    @pytest.mark.asyncio
    async def test_process_multi_intent_partial_none(self) -> None:
        """测试部分意图返回None"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = [
            IntentResult(
                primary_intent=IntentCategory.ORDER,
                secondary_intent=IntentAction.QUERY,
                confidence=0.9,
                slots={"order_id": "123"},
            ),
            None,  # 第二个意图返回None
        ]

        processor = MultiIntentProcessor(classifier=mock_classifier)
        result = await processor.process("查询订单顺便申请退款")

        assert result.is_multi_intent is True
        assert len(result.sub_intents) == 1
        assert result.sub_intents[0].primary_intent == IntentCategory.ORDER

    @pytest.mark.asyncio
    async def test_process_classifier_exception_single_intent(self) -> None:
        """测试单意图时分类器异常处理"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = Exception("分类器错误")

        processor = MultiIntentProcessor(classifier=mock_classifier)
        result = await processor.process("查询订单")

        # 应该优雅降级，返回空结果
        assert result.is_multi_intent is False
        assert result.sub_intents == []

    @pytest.mark.asyncio
    async def test_process_classifier_exception_multi_intent(self) -> None:
        """测试多意图时分类器异常处理"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = Exception("分类器错误")

        processor = MultiIntentProcessor(classifier=mock_classifier)
        result = await processor.process("查询订单顺便申请退款")

        # 应该优雅降级，返回空子意图列表
        assert result.is_multi_intent is True
        assert result.sub_intents == []

    @pytest.mark.asyncio
    async def test_process_classifier_partial_exception(self) -> None:
        """测试部分segment分类异常，其他正常处理"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = [
            IntentResult(
                primary_intent=IntentCategory.ORDER,
                secondary_intent=IntentAction.QUERY,
                confidence=0.9,
                slots={"order_id": "123"},
            ),
            Exception("第二个segment失败"),
        ]

        processor = MultiIntentProcessor(classifier=mock_classifier)
        result = await processor.process("查询订单顺便申请退款")

        # 应该返回第一个成功的结果
        assert result.is_multi_intent is True
        assert len(result.sub_intents) == 1
        assert result.sub_intents[0].primary_intent == IntentCategory.ORDER


class TestIntentClassifierProtocol:
    """测试意图分类器协议"""

    def test_protocol_definition(self) -> None:
        """测试协议定义存在"""
        # 验证协议可以被引用
        assert callable(IntentClassifierProtocol)

    @pytest.mark.asyncio
    async def test_mock_implements_protocol(self) -> None:
        """测试mock对象符合协议"""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.9,
        )

        # 应该可以正常工作
        result = await mock_classifier.classify("测试")
        assert result is not None
        assert result.primary_intent == IntentCategory.ORDER
