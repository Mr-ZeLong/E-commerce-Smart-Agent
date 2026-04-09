"""测试澄清引擎"""

import pytest

from app.intent.clarification import ClarificationEngine
from app.intent.models import ClarificationState, IntentAction, IntentCategory, IntentResult
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
            filled_slots=[],
            suggestions={},
        )

        response = await engine.generate_clarification(initial_state, validation)

        assert "订单号" in response.response
        assert initial_state.pending_slot == "order_sn"
        assert "order_sn" in initial_state.asked_slots
        assert initial_state.clarification_round == 1

    @pytest.mark.asyncio
    async def test_clarification_complete_when_no_missing_slots(self, engine, initial_state):
        """测试无缺失槽位时返回完成"""
        validation = SlotValidationResult(
            is_complete=True,
            missing_p0_slots=[],
            missing_p1_slots=[],
            missing_p2_slots=[],
            filled_slots=["order_sn"],
            suggestions={},
        )

        response = await engine.generate_clarification(initial_state, validation)

        assert response.is_complete is True
        assert response.collected_slots == initial_state.collected_slots

    @pytest.mark.asyncio
    async def test_max_rounds_response(self, engine, initial_state):
        """测试达到最大澄清轮次时的响应"""
        # 设置已达到最大轮次
        initial_state.clarification_round = 3

        validation = SlotValidationResult(
            is_complete=False,
            missing_p0_slots=["order_sn"],
            missing_p1_slots=[],
            missing_p2_slots=[],
            filled_slots=[],
            suggestions={},
        )

        response = await engine.generate_clarification(initial_state, validation)

        assert response.is_complete is True
        assert "主要信息" in response.response
        assert response.collected_slots == initial_state.collected_slots


class TestUserRefusalHandling:
    def test_detect_refusal(self, engine):
        """测试检测用户拒绝"""
        assert engine._is_user_refusal("我不知道") is True
        assert engine._is_user_refusal("不记得了") is True
        assert engine._is_user_refusal("SN001") is False

    @pytest.mark.asyncio
    async def test_handle_refusal_skip_strategy(self, engine, initial_state):
        """测试拒绝处理 - 跳过策略"""
        initial_state.pending_slot = "order_sn"
        initial_state.clarification_round = 2  # 超过第一轮，跳过optional策略

        response = await engine._handle_refusal(initial_state, "我不知道")

        # 验证跳过策略被应用
        assert "order_sn" in initial_state.user_refused_slots
        assert initial_state.pending_slot is None
        assert "跳过" in response.response or "继续" in response.response

    @pytest.mark.asyncio
    async def test_handle_refusal_infer_strategy(self, engine, initial_state):
        """测试拒绝处理 - 推断策略 (reason_category)"""
        initial_state.pending_slot = "reason_category"
        initial_state.clarification_round = 2

        response = await engine._handle_refusal(initial_state, "不知道")

        # 验证推断策略被应用
        assert initial_state.collected_slots.get("reason_category") == "其他"
        assert initial_state.pending_slot is None
        assert "其他原因" in response.response

    @pytest.mark.asyncio
    async def test_generate_question_with_suggestions(self, engine, initial_state):
        """测试生成带建议选项的问题"""
        validation = SlotValidationResult(
            is_complete=False,
            missing_p0_slots=["action_type"],
            missing_p1_slots=[],
            missing_p2_slots=[],
            filled_slots=[],
            suggestions={"action_type": ["REFUND", "EXCHANGE", "REPAIR"]},
        )

        response = await engine.generate_clarification(initial_state, validation)

        assert "action_type" in initial_state.pending_slot
        # 验证建议选项显示在问题中
        assert "可选" in response.response or "REFUND" in response.response or "退货" in response.response
