"""澄清引擎

生成渐进式追问问题，智能推荐候选值，处理用户拒绝（4种降级策略）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.intent.models import ClarificationState, IntentResult
from app.intent.slot_validator import SlotValidationResult, SlotValidator


@dataclass
class ClarificationResponse:
    """澄清响应"""
    response: str
    state: ClarificationState
    is_complete: bool = False
    collected_slots: dict[str, Any] | None = None


class ClarificationEngine:
    """澄清引擎"""

    # 槽位询问模板
    SLOT_QUESTION_TEMPLATES: dict[str, str] = {
        "order_sn": "请问您的订单号是多少？",
        "action_type": "请问您需要办理什么业务？（退货/换货/维修）",
        "reason_category": "请问是什么原因呢？",
        "product_name": "请问是哪个商品呢？",
        "policy_topic": "请问您想了解哪方面的政策？",
        "modify_field": "请问您需要修改什么信息？",
        "new_value": "请问新的值是什么？",
    }

    # 用户拒绝关键词
    REFUSAL_KEYWORDS = [
        "不知道", "不记得", "没有", "不想说", "不方便",
        "算了", "不用了", "不用", "别问了", "随便",
    ]

    def __init__(self, slot_validator: SlotValidator | None = None):
        self.slot_validator = slot_validator or SlotValidator()
        self.degradation_strategies = [
            self._degradation_optional,      # 策略1: 设为可选
            self._degradation_infer,         # 策略2: 智能推断
            self._degradation_skip,          # 策略3: 跳过
            self._degradation_escalate,      # 策略4: 转人工
        ]

    async def generate_clarification(
        self,
        state: ClarificationState,
        validation_result: SlotValidationResult,
    ) -> ClarificationResponse:
        """
        生成澄清问题

        Args:
            state: 当前澄清状态
            validation_result: 槽位验证结果

        Returns:
            ClarificationResponse: 澄清响应
        """
        # 检查是否还能继续澄清
        if not state.can_continue_clarification():
            return self._build_max_rounds_response(state)

        # 获取下一个缺失槽位
        next_slot = self.slot_validator.get_next_missing_slot(validation_result)

        if not next_slot:
            # 所有槽位已收集完成
            return ClarificationResponse(
                response="",
                state=state,
                is_complete=True,
                collected_slots=state.collected_slots,
            )

        # 生成问题
        question = self._generate_question(
            next_slot, validation_result.suggestions.get(next_slot, [])
        )

        # 更新状态
        state.pending_slot = next_slot
        state.asked_slots.append(next_slot)
        state.increment_round()

        return ClarificationResponse(
            response=question,
            state=state,
            is_complete=False,
        )

    async def handle_user_response(
        self,
        state: ClarificationState,
        user_response: str,
        validation_result: SlotValidationResult | None = None,
    ) -> ClarificationResponse:
        """
        处理用户回复

        Args:
            state: 当前澄清状态
            user_response: 用户回复
            validation_result: 槽位验证结果（可选）

        Returns:
            ClarificationResponse: 处理结果
        """
        # 检测用户拒绝
        if self._is_user_refusal(user_response):
            return await self._handle_refusal(state, user_response)

        # 提取槽位值（简化版，实际可用LLM提取）
        if state.pending_slot:
            state.collected_slots[state.pending_slot] = user_response.strip()
            state.clarification_history.append({
                "slot": state.pending_slot,
                "value": user_response.strip(),
                "type": "provided",
            })
            state.pending_slot = None

        # 检查是否完成
        if validation_result:
            # 重新验证

            # 构建临时结果用于验证
            temp_result = IntentResult(
                primary_intent=state.current_intent.primary_intent if state.current_intent else None,  # type: ignore
                secondary_intent=state.current_intent.secondary_intent if state.current_intent else None,  # type: ignore
                slots=state.collected_slots,
            )

            new_validation = self.slot_validator.validate(temp_result)

            if new_validation.is_complete:
                return ClarificationResponse(
                    response="",
                    state=state,
                    is_complete=True,
                    collected_slots=state.collected_slots,
                )

        # 继续澄清
        if validation_result:
            return await self.generate_clarification(state, validation_result)

        return ClarificationResponse(
            response="明白了，还有其他信息需要补充吗？",
            state=state,
            is_complete=False,
        )

    def _generate_question(self, slot_name: str, suggestions: list[str]) -> str:
        """生成询问问题"""
        base_question = self.SLOT_QUESTION_TEMPLATES.get(
            slot_name, f"请问{slot_name}是什么？"
        )

        if suggestions:
            suggestion_text = " / ".join(suggestions[:4])  # 最多4个选项
            return f"{base_question}（可选：{suggestion_text}）"

        return base_question

    def _is_user_refusal(self, response: str) -> bool:
        """检测用户是否拒绝回答"""
        response_lower = response.lower()
        return any(keyword in response_lower for keyword in self.REFUSAL_KEYWORDS)

    async def _handle_refusal(
        self, state: ClarificationState, user_response: str
    ) -> ClarificationResponse:
        """处理用户拒绝 - 应用降级策略"""
        if not state.pending_slot:
            return ClarificationResponse(
                response="好的，我们继续。",
                state=state,
                is_complete=False,
            )

        # 按顺序尝试降级策略
        for strategy in self.degradation_strategies:
            result = await strategy(state, state.pending_slot, user_response)
            if result:
                return result

        # 默认：跳过
        state.user_refused_slots.append(state.pending_slot)
        state.pending_slot = None
        return ClarificationResponse(
            response="好的，我们先跳过这个问题。",
            state=state,
            is_complete=False,
        )

    async def _degradation_optional(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        """降级策略1: 设为可选，询问是否跳过"""
        if state.clarification_round <= 1:
            return ClarificationResponse(
                response=f"这个信息不是必须的，我们可以先跳过。您确定不需要提供吗？",
                state=state,
                is_complete=False,
            )
        return None

    async def _degradation_infer(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        """降级策略2: 智能推断（简化版）"""
        # 实际实现中可以使用LLM推断
        if slot == "reason_category":
            state.collected_slots[slot] = "其他"
            state.pending_slot = None
            return ClarificationResponse(
                response="好的，我记为其他原因。",
                state=state,
                is_complete=False,
            )
        return None

    async def _degradation_skip(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        """降级策略3: 直接跳过"""
        state.user_refused_slots.append(slot)
        state.pending_slot = None
        return ClarificationResponse(
            response="好的，我们先继续。",
            state=state,
            is_complete=False,
        )

    async def _degradation_escalate(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        """降级策略4: 转人工"""
        return ClarificationResponse(
            response="这个问题比较复杂，我为您转接人工客服。",
            state=state,
            is_complete=True,
            collected_slots=state.collected_slots,
        )

    def _build_max_rounds_response(self, state: ClarificationState) -> ClarificationResponse:
        """达到最大澄清轮次的响应"""
        return ClarificationResponse(
            response="我已经了解了主要信息，现在就为您处理。",
            state=state,
            is_complete=True,
            collected_slots=state.collected_slots,
        )
