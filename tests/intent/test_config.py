"""测试意图配置"""

from app.intent.config import (
    TERTIARY_INTENT_CONFIG,
    check_intent_compatibility,
    get_required_slots,
    get_slot_priority,
    validate_tertiary_intent,
)
from app.intent.models import IntentAction, IntentCategory, SlotPriority


def test_tertiary_intent_config_exists():
    assert ("AFTER_SALES", "APPLY") in TERTIARY_INTENT_CONFIG
    assert ("ORDER", "QUERY") in TERTIARY_INTENT_CONFIG


def test_validate_tertiary_intent_valid():
    result = validate_tertiary_intent(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "REFUND",
    )
    assert result is True


def test_validate_tertiary_intent_invalid():
    result = validate_tertiary_intent(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "INVALID_INTENT",
    )
    assert result is False


def test_validate_tertiary_intent_none():
    result = validate_tertiary_intent(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        None,
    )
    assert result is True


def test_get_slot_priority_p0():
    priority = get_slot_priority(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "order_sn",
    )
    assert priority == SlotPriority.P0


def test_get_slot_priority_p1():
    priority = get_slot_priority(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "reason_category",
    )
    assert priority == SlotPriority.P1


def test_get_slot_priority_not_found():
    priority = get_slot_priority(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
        "nonexistent_slot",
    )
    assert priority is None


def test_get_required_slots():
    slots = get_required_slots(
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
    )
    assert "order_sn" in slots
    assert "action_type" in slots


def test_check_intent_compatibility_same():
    result = check_intent_compatibility(
        "ORDER/QUERY",
        "ORDER/QUERY",
    )
    assert result is True


def test_check_intent_compatibility_compatible():
    result = check_intent_compatibility(
        "AFTER_SALES/APPLY",
        "AFTER_SALES/CONSULT",
    )
    assert result is True


def test_check_intent_compatibility_incompatible():
    result = check_intent_compatibility(
        "ORDER/QUERY",
        "ACCOUNT/QUERY",
    )
    assert result is False
