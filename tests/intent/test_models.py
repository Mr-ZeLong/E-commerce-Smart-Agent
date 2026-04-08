"""测试数据模型"""

import pytest
from datetime import datetime

from app.intent.models import (
    IntentCategory,
    IntentAction,
    SlotPriority,
    Slot,
    IntentResult,
    ClarificationState,
)


class TestIntentCategory:
    def test_enum_values(self):
        """测试所有12个IntentCategory值"""
        expected_values = {
            "ORDER", "AFTER_SALES", "POLICY", "ACCOUNT",
            "PROMOTION", "PAYMENT", "LOGISTICS", "PRODUCT",
            "RECOMMENDATION", "CART", "COMPLAINT", "OTHER"
        }
        actual_values = {e.value for e in IntentCategory}
        assert actual_values == expected_values

    def test_enum_comparison(self):
        assert IntentCategory.ORDER == IntentCategory.ORDER
        assert IntentCategory.ORDER != IntentCategory.POLICY


class TestIntentAction:
    def test_enum_values(self):
        """测试所有8个IntentAction值"""
        expected_values = {
            "QUERY", "APPLY", "MODIFY", "CANCEL",
            "CONSULT", "ADD", "REMOVE", "COMPARE"
        }
        actual_values = {e.value for e in IntentAction}
        assert actual_values == expected_values


class TestSlotPriority:
    def test_enum_values(self):
        assert SlotPriority.P0 == "P0"
        assert SlotPriority.P1 == "P1"
        assert SlotPriority.P2 == "P2"


class TestSlot:
    def test_slot_creation(self):
        slot = Slot(
            name="order_sn",
            description="订单号",
            priority=SlotPriority.P0,
            required=True,
            extractor="order_sn_extractor",
        )
        assert slot.name == "order_sn"
        assert slot.priority == SlotPriority.P0


class TestIntentResult:
    def test_intent_result_creation(self):
        result = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.95,
            slots={"order_sn": "SN12345"},
        )
        assert result.primary_intent == IntentCategory.ORDER
        assert result.confidence == 0.95

    def test_to_dict(self):
        result = IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            tertiary_intent="latest",
            confidence=0.95,
            slots={"order_sn": "SN12345"},
            missing_slots=["time_range"],
            needs_clarification=True,
            clarification_question="请问查询哪个时间段的订单？",
            raw_query="查订单",
        )
        data = result.to_dict()
        assert data["primary_intent"] == "ORDER"
        assert data["secondary_intent"] == "QUERY"
        assert data["tertiary_intent"] == "latest"
        assert data["confidence"] == 0.95
        assert data["needs_clarification"] is True


class TestClarificationState:
    def test_initial_state(self):
        state = ClarificationState(session_id="test_session")
        assert state.session_id == "test_session"
        assert state.clarification_round == 0
        assert state.can_continue_clarification() is True

    def test_increment_round(self):
        state = ClarificationState(session_id="test_session")
        state.increment_round()
        assert state.clarification_round == 1
        assert state.can_continue_clarification() is True

    def test_max_rounds_reached(self):
        state = ClarificationState(
            session_id="test_session",
            max_clarification_rounds=2,
            clarification_round=2,
        )
        assert state.can_continue_clarification() is False
