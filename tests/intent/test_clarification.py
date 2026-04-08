"""测试澄清引擎"""

import pytest

from app.intent.clarification import ClarificationEngine
from app.intent.models import ClarificationState, IntentCategory, IntentAction, IntentResult
from app.intent.slot_validator import SlotValidationResult


@pytest.fixture
def engine():
    return ClarificationEngine()


@pytest.fixture
def initial_state():
    return ClarificationState(
        session_id="test_123",
        current_intent=IntentResult(
            primary_intent=IntentCategory.AFTER_SALES,
            secondary_intent=IntentAction.APPLY,
        ),
    )


class TestClarificationGeneration:
    @pytest.mark.asyncio
    async def test_generate_clarification_for_missing_slot(self, engine, initial_state):
        """测试为缺失槽位生成澄清问题"""
        validation = SlotValidationResult(
            is_complete=False,
            missing_p0_slots=["order_sn"],
            missing_p1_slots=[],
            missing_p2_slots=[],
            filled_slots={},
            suggestions={},
        )

        response = await engine.generate_clarification(initial_state, validation)

        assert "订单号" in response.response
        assert initial_state.pending_slot == "order_sn"

    @pytest.mark.asyncio
    async def test_clarification_complete_when_no_missing_slots(self, engine, initial_state):
        """测试无缺失槽位时返回完成"""
        validation = SlotValidationResult(
            is_complete=True,
            missing_p0_slots=[],
            missing_p1_slots=[],
            missing_p2_slots=[],
            filled_slots={"order_sn": "SN001"},
            suggestions={},
        )

        response = await engine.generate_clarification(initial_state, validation)

        assert response.is_complete is True


class TestUserRefusalHandling:
    @pytest.mark.asyncio
    async def test_detect_refusal(self, engine):
        """测试检测用户拒绝"""
        assert engine._is_user_refusal("我不知道") is True
        assert engine._is_user_refusal("不记得了") is True
        assert engine._is_user_refusal("SN001") is False

    @pytest.mark.asyncio
    async def test_handle_refusal_with_degradation(self, engine, initial_state):
        """测试处理用户拒绝"""
        initial_state.pending_slot = "order_sn"

        response = await engine._handle_refusal(initial_state, "我不知道")

        assert "跳过" in response.response or "转接" in response.response
