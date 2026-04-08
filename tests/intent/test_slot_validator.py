"""槽位验证器测试"""

import pytest

from app.intent.models import IntentCategory, IntentAction
from app.intent.slot_validator import SlotValidator, SlotValidationResult


class TestSlotValidationResult:
    """测试SlotValidationResult数据类"""

    def test_default_values(self):
        """测试默认值"""
        result = SlotValidationResult(is_complete=True)
        assert result.is_complete is True
        assert result.missing_slots == []
        assert result.p0_missing == []
        assert result.p1_missing == []
        assert result.p2_missing == []
        assert result.suggestions == {}

    def test_custom_values(self):
        """测试自定义值"""
        result = SlotValidationResult(
            is_complete=False,
            missing_slots=["order_sn"],
            p0_missing=["order_sn"],
            p1_missing=["reason_category"],
            p2_missing=["reason_detail"],
            suggestions={"action_type": ["退款", "换货"]},
        )
        assert result.is_complete is False
        assert result.missing_slots == ["order_sn"]
        assert result.p0_missing == ["order_sn"]
        assert result.p1_missing == ["reason_category"]
        assert result.p2_missing == ["reason_detail"]
        assert result.suggestions == {"action_type": ["退款", "换货"]}


class TestSlotValidator:
    """测试SlotValidator类"""

    @pytest.fixture
    def validator(self):
        """创建验证器实例"""
        return SlotValidator()

    def test_init(self, validator):
        """测试初始化"""
        assert validator is not None
        assert isinstance(validator.SLOT_SUGGESTIONS, dict)

    def test_validate_complete_slots(self, validator):
        """测试槽位完整的情况"""
        slots = {
            "order_sn": "123456789",
            "action_type": "退款",
        }
        result = validator.validate(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert result.is_complete is True
        assert result.p0_missing == []
        assert result.missing_slots == ["reason_category", "specific_item", "reason_detail", "preferred_contact"]

    def test_validate_missing_p0_slot(self, validator):
        """测试缺少P0槽位"""
        slots = {
            "action_type": "退款",
            # 缺少 order_sn
        }
        result = validator.validate(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert result.is_complete is False
        assert "order_sn" in result.p0_missing
        assert "order_sn" in result.missing_slots

    def test_validate_multiple_missing_p0(self, validator):
        """测试缺少多个P0槽位"""
        slots = {}
        result = validator.validate(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert result.is_complete is False
        assert "order_sn" in result.p0_missing
        assert "action_type" in result.p0_missing

    def test_validate_with_none_and_empty_values(self, validator):
        """测试None和空字符串值"""
        slots = {
            "order_sn": None,
            "action_type": "",
        }
        result = validator.validate(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert result.is_complete is False
        assert "order_sn" in result.p0_missing
        assert "action_type" in result.p0_missing

    def test_validate_priority_separation(self, validator):
        """测试优先级分离"""
        slots = {
            "order_sn": "123456789",
            "action_type": "退款",
            # P1槽位未填充
        }
        result = validator.validate(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert result.is_complete is True  # P0完整
        assert result.p0_missing == []
        assert "reason_category" in result.p1_missing
        assert "specific_item" in result.p1_missing

    def test_get_next_missing_slot_p0_priority(self, validator):
        """测试获取下一个缺失槽位（P0优先）"""
        slots = {
            "action_type": "退款",
            # 缺少 order_sn (P0)
        }
        next_slot = validator.get_next_missing_slot(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert next_slot == "order_sn"

    def test_get_next_missing_slot_p1_when_p0_complete(self, validator):
        """测试P0完整时获取P1槽位"""
        slots = {
            "order_sn": "123456789",
            "action_type": "退款",
        }
        next_slot = validator.get_next_missing_slot(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert next_slot in ["reason_category", "specific_item"]

    def test_get_next_missing_slot_with_exclude(self, validator):
        """测试排除特定槽位"""
        slots = {
            "order_sn": "123456789",
            # 缺少 action_type
        }
        next_slot = validator.get_next_missing_slot(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
            exclude_slots=["action_type"],
        )
        # action_type被排除，应该返回P1槽位
        assert next_slot in ["reason_category", "specific_item"]

    def test_get_next_missing_slot_no_missing(self, validator):
        """测试没有缺失槽位"""
        slots = {
            "order_sn": "123456789",
            "action_type": "退款",
            "reason_category": "质量问题",
            "specific_item": "商品A",
            "reason_detail": "有瑕疵",
            "preferred_contact": "电话",
        }
        next_slot = validator.get_next_missing_slot(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert next_slot is None

    def test_merge_slots_basic(self, validator):
        """测试基本槽位合并"""
        existing = {"order_sn": "123", "action_type": "退款"}
        new = {"reason_category": "质量问题"}
        merged = validator.merge_slots(existing, new)
        assert merged["order_sn"] == "123"
        assert merged["action_type"] == "退款"
        assert merged["reason_category"] == "质量问题"

    def test_merge_slots_overwrite(self, validator):
        """测试槽位合并覆盖"""
        existing = {"order_sn": "123", "action_type": "退款"}
        new = {"action_type": "换货"}
        merged = validator.merge_slots(existing, new, overwrite=True)
        assert merged["action_type"] == "换货"

    def test_merge_slots_no_overwrite(self, validator):
        """测试槽位合并不覆盖"""
        existing = {"order_sn": "123", "action_type": "退款"}
        new = {"action_type": "换货"}
        merged = validator.merge_slots(existing, new, overwrite=False)
        assert merged["action_type"] == "退款"

    def test_merge_slots_skip_empty(self, validator):
        """测试跳过空值"""
        existing = {"order_sn": "123"}
        new = {"action_type": "", "reason_category": None}
        merged = validator.merge_slots(existing, new)
        assert "action_type" not in merged
        assert "reason_category" not in merged

    def test_get_slot_suggestions(self, validator):
        """测试获取槽位推荐值"""
        suggestions = validator.get_slot_suggestions("action_type")
        assert "退款" in suggestions
        assert "换货" in suggestions
        assert "维修" in suggestions

    def test_get_slot_suggestions_not_exist(self, validator):
        """测试获取不存在的槽位推荐值"""
        suggestions = validator.get_slot_suggestions("non_existent_slot")
        assert suggestions == []

    def test_validate_with_suggestions(self, validator):
        """测试验证时生成推荐值"""
        slots = {}
        result = validator.validate(
            IntentCategory.AFTER_SALES,
            IntentAction.APPLY,
            slots,
        )
        assert "action_type" in result.suggestions
        assert "退款" in result.suggestions["action_type"]

    def test_validate_different_intent(self, validator):
        """测试不同意图组合的验证"""
        # ORDER/QUERY
        slots = {"order_sn": "123"}
        result = validator.validate(
            IntentCategory.ORDER,
            IntentAction.QUERY,
            slots,
        )
        assert result.is_complete is True  # P0只有order_sn

        # PRODUCT/QUERY
        slots = {"product_name": "iPhone"}
        result = validator.validate(
            IntentCategory.PRODUCT,
            IntentAction.QUERY,
            slots,
        )
        assert result.is_complete is True

    def test_get_priority(self, validator):
        """测试获取槽位优先级"""
        priority = validator.get_priority("order_sn")
        assert priority is not None

        priority = validator.get_priority("non_existent")
        assert priority is None

    def test_validate_empty_config(self, validator):
        """测试没有配置的情况"""
        slots = {}
        result = validator.validate(
            IntentCategory.OTHER,
            IntentAction.QUERY,
            slots,
        )
        assert result.is_complete is True  # 没有配置，视为完整
        assert result.missing_slots == []
