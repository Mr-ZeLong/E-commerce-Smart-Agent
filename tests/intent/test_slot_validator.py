"""槽位验证器测试"""

import pytest

from app.intent.models import IntentCategory, IntentAction, IntentResult
from app.intent.slot_validator import SlotValidator, SlotValidationResult


class TestSlotValidationResult:
    """测试SlotValidationResult数据类"""

    def test_default_values(self) -> None:
        """测试默认值"""
        result = SlotValidationResult(is_complete=True)
        assert result.is_complete is True
        assert result.missing_slots == []
        assert result.missing_p0_slots == []
        assert result.missing_p1_slots == []
        assert result.missing_p2_slots == []
        assert result.filled_slots == []
        assert result.suggestions == {}

    def test_custom_values(self) -> None:
        """测试自定义值"""
        result = SlotValidationResult(
            is_complete=False,
            missing_slots=["order_sn"],
            missing_p0_slots=["order_sn"],
            missing_p1_slots=["reason_category"],
            missing_p2_slots=["reason_detail"],
            filled_slots=["action_type"],
            suggestions={"action_type": ["REFUND", "EXCHANGE"]},
        )
        assert result.is_complete is False
        assert result.missing_slots == ["order_sn"]
        assert result.missing_p0_slots == ["order_sn"]
        assert result.missing_p1_slots == ["reason_category"]
        assert result.missing_p2_slots == ["reason_detail"]
        assert result.filled_slots == ["action_type"]
        assert result.suggestions == {"action_type": ["REFUND", "EXCHANGE"]}

    def test_repr_complete(self) -> None:
        """测试__repr__方法 - 完整状态"""
        result = SlotValidationResult(is_complete=True)
        assert "完整" in repr(result)
        assert "SlotValidationResult" in repr(result)

    def test_repr_incomplete(self) -> None:
        """测试__repr__方法 - 不完整状态"""
        result = SlotValidationResult(
            is_complete=False,
            missing_slots=["order_sn", "action_type"],
        )
        repr_str = repr(result)
        assert "缺失 2 个槽位" in repr_str
        assert "SlotValidationResult" in repr_str


class TestSlotValidator:
    """测试SlotValidator类"""

    @pytest.fixture
    def validator(self) -> SlotValidator:
        """创建验证器实例"""
        return SlotValidator()

    def test_init(self, validator: SlotValidator) -> None:
        """测试初始化"""
        assert validator is not None
        assert isinstance(validator.SLOT_SUGGESTIONS, dict)

    def test_validate_complete_slots(self, validator: SlotValidator) -> None:
        """测试槽位完整的情况"""
        result = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={
                "order_sn": "123456789",
                "action_type": "REFUND",
            },
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is True
        assert validation_result.missing_p0_slots == []
        assert validation_result.filled_slots == ["order_sn", "action_type"]

    def test_validate_missing_p0_slot(self, validator: SlotValidator) -> None:
        """测试缺少P0槽位"""
        result = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={
                "action_type": "REFUND",
                # 缺少 order_sn
            },
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is False
        assert "order_sn" in validation_result.missing_p0_slots
        assert "order_sn" in validation_result.missing_slots

    def test_validate_multiple_missing_p0(self, validator: SlotValidator) -> None:
        """测试缺少多个P0槽位"""
        result = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={},
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is False
        assert "order_sn" in validation_result.missing_p0_slots
        assert "action_type" in validation_result.missing_p0_slots

    def test_validate_with_none_and_empty_values(self, validator: SlotValidator) -> None:
        """测试None和空字符串值"""
        result = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={
                "order_sn": None,
                "action_type": "",
            },
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is False
        assert "order_sn" in validation_result.missing_p0_slots
        assert "action_type" in validation_result.missing_p0_slots

    def test_validate_priority_separation(self, validator: SlotValidator) -> None:
        """测试优先级分离"""
        result = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={
                "order_sn": "123456789",
                "action_type": "REFUND",
                # P1槽位未填充
            },
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is True  # P0完整
        assert validation_result.missing_p0_slots == []
        assert "reason_category" in validation_result.missing_p1_slots
        assert "specific_item" in validation_result.missing_p1_slots

    def test_get_next_missing_slot_p0_priority(self, validator: SlotValidator) -> None:
        """测试获取下一个缺失槽位（P0优先）"""
        validation_result = SlotValidationResult(
            is_complete=False,
            missing_p0_slots=["order_sn"],
            missing_p1_slots=["reason_category"],
            missing_p2_slots=["reason_detail"],
        )
        next_slot = validator.get_next_missing_slot(validation_result)
        assert next_slot == "order_sn"

    def test_get_next_missing_slot_p1_when_p0_complete(self, validator: SlotValidator) -> None:
        """测试P0完整时获取P1槽位"""
        validation_result = SlotValidationResult(
            is_complete=True,
            missing_p0_slots=[],
            missing_p1_slots=["reason_category", "specific_item"],
            missing_p2_slots=[],
        )
        next_slot = validator.get_next_missing_slot(validation_result)
        assert next_slot in ["reason_category", "specific_item"]

    def test_get_next_missing_slot_no_missing(self, validator: SlotValidator) -> None:
        """测试没有缺失槽位"""
        validation_result = SlotValidationResult(
            is_complete=True,
            missing_p0_slots=[],
            missing_p1_slots=[],
            missing_p2_slots=[],
        )
        next_slot = validator.get_next_missing_slot(validation_result)
        assert next_slot is None

    def test_merge_slots_basic(self, validator: SlotValidator) -> None:
        """测试基本槽位合并"""
        existing = {"order_sn": "123", "action_type": "REFUND"}
        new = {"reason_category": "质量问题"}
        merged = validator.merge_slots(existing, new)
        assert merged["order_sn"] == "123"
        assert merged["action_type"] == "REFUND"
        assert merged["reason_category"] == "质量问题"

    def test_merge_slots_overwrite(self, validator: SlotValidator) -> None:
        """测试槽位合并覆盖"""
        existing = {"order_sn": "123", "action_type": "REFUND"}
        new = {"action_type": "EXCHANGE"}
        merged = validator.merge_slots(existing, new, overwrite=True)
        assert merged["action_type"] == "EXCHANGE"

    def test_merge_slots_no_overwrite(self, validator: SlotValidator) -> None:
        """测试槽位合并不覆盖"""
        existing = {"order_sn": "123", "action_type": "REFUND"}
        new = {"action_type": "EXCHANGE"}
        merged = validator.merge_slots(existing, new, overwrite=False)
        assert merged["action_type"] == "REFUND"

    def test_merge_slots_skip_empty(self, validator: SlotValidator) -> None:
        """测试跳过空值"""
        existing = {"order_sn": "123"}
        new = {"action_type": "", "reason_category": None}
        merged = validator.merge_slots(existing, new)
        assert "action_type" not in merged
        assert "reason_category" not in merged

    def test_get_slot_suggestions(self, validator: SlotValidator) -> None:
        """测试获取槽位推荐值"""
        suggestions = validator.get_slot_suggestions("action_type")
        assert "REFUND" in suggestions
        assert "EXCHANGE" in suggestions
        assert "REPAIR" in suggestions

    def test_get_slot_suggestions_not_exist(self, validator: SlotValidator) -> None:
        """测试获取不存在的槽位推荐值"""
        suggestions = validator.get_slot_suggestions("non_existent_slot")
        assert suggestions == []

    def test_validate_with_suggestions(self, validator: SlotValidator) -> None:
        """测试验证时生成推荐值"""
        result = IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
            slots={},
        )
        validation_result = validator.validate(result)
        assert "action_type" in validation_result.suggestions
        assert "REFUND" in validation_result.suggestions["action_type"]

    def test_validate_different_intent(self, validator: SlotValidator) -> None:
        """测试不同意图组合的验证"""
        # ORDER/QUERY
        result = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            slots={"order_sn": "123"},
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is True  # P0只有order_sn

        # PRODUCT/QUERY
        result = IntentResult(
            primary_intent=IntentCategory.PRODUCT,
            secondary_intent=IntentAction.QUERY,
            slots={"product_name": "iPhone"},
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is True

    def test_get_priority(self, validator: SlotValidator) -> None:
        """测试获取槽位优先级"""
        priority = validator.get_priority("order_sn")
        assert priority is not None

        priority = validator.get_priority("non_existent")
        assert priority is None

    def test_validate_empty_config(self, validator: SlotValidator) -> None:
        """测试没有配置的情况"""
        result = IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.QUERY,
            slots={},
        )
        validation_result = validator.validate(result)
        assert validation_result.is_complete is True  # 没有配置，视为完整
        assert validation_result.missing_slots == []

    def test_is_empty_value(self, validator: SlotValidator) -> None:
        """测试_is_empty_value辅助方法"""
        assert validator._is_empty_value(None) is True
        assert validator._is_empty_value("") is True
        assert validator._is_empty_value("value") is False
        assert validator._is_empty_value(0) is False
        assert validator._is_empty_value([]) is False
