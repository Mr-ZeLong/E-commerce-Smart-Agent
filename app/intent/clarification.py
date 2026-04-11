from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.intent.models import ClarificationState, IntentResult
from app.intent.slot_validator import SlotValidationResult, SlotValidator


@dataclass
class ClarificationResponse:
    response: str
    state: ClarificationState
    is_complete: bool = False
    collected_slots: dict[str, Any] | None = None


class ClarificationEngine:
    MAX_SUGGESTIONS = 4

    SLOT_QUESTION_TEMPLATES: dict[str, str] = {
        "order_sn": "请问您的订单号是多少？",
        "action_type": "请问您需要办理什么业务？（退货/换货/维修）",
        "reason_category": "请问是什么原因呢？",
        "product_name": "请问是哪个商品呢？",
        "policy_topic": "请问您想了解哪方面的政策？",
        "modify_field": "请问您需要修改什么信息？",
        "new_value": "请问新的值是什么？",
    }

    REFUSAL_KEYWORDS = [
        "不知道",
        "不记得",
        "没有",
        "不想说",
        "不方便",
        "算了",
        "不用了",
        "不用",
        "别问了",
        "随便",
    ]

    def __init__(self, slot_validator: SlotValidator | None = None):
        self.slot_validator = slot_validator or SlotValidator()
        self.degradation_strategies = [
            self._degradation_optional,
            self._degradation_infer,
            self._degradation_skip,
            self._degradation_escalate,
        ]

    async def generate_clarification(
        self, state: ClarificationState, validation_result: SlotValidationResult
    ) -> ClarificationResponse:
        if not state.can_continue_clarification():
            return self._build_max_rounds_response(state)

        next_slot = self.slot_validator.get_next_missing_slot(validation_result)
        if not next_slot:
            return ClarificationResponse(
                response="", state=state, is_complete=True, collected_slots=state.collected_slots
            )

        question = self._generate_question(
            next_slot, validation_result.suggestions.get(next_slot, [])
        )
        state.pending_slot = next_slot
        state.asked_slots.append(next_slot)
        state.increment_round()

        return ClarificationResponse(response=question, state=state, is_complete=False)

    async def handle_user_response(
        self,
        state: ClarificationState,
        user_response: str,
        validation_result: SlotValidationResult | None = None,
    ) -> ClarificationResponse:
        if self._is_user_refusal(user_response):
            return await self._handle_refusal(state, user_response)

        if state.pending_slot:
            extracted = self._extract_slot_value(state.pending_slot, user_response)
            state.collected_slots[state.pending_slot] = extracted
            state.clarification_history.append(
                {"slot": state.pending_slot, "value": extracted, "type": "provided"}
            )
            state.pending_slot = None

        if validation_result and state.current_intent:
            temp_result = IntentResult(
                primary_intent=state.current_intent.primary_intent,
                secondary_intent=state.current_intent.secondary_intent,
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

        if validation_result:
            return await self.generate_clarification(state, validation_result)

        return ClarificationResponse(
            response="明白了，还有其他信息需要补充吗？", state=state, is_complete=False
        )

    def _extract_slot_value(self, slot_name: str, response: str) -> str:
        # Strip common prefixes and punctuation to extract the actual slot value
        cleaned = response.strip()
        # Remove common Chinese filler phrases
        patterns = [
            rf".*?(?:我的|这个)?\s*{re.escape(slot_name)}\s*(?:是|为|：|:|=)\s*(.+?)(?:[。，；;！!]|$)",
            r"(?:是|为)\s*(.+?)(?:[。，；;！!]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return cleaned

    def _generate_question(self, slot_name: str, suggestions: list[str]) -> str:
        base = self.SLOT_QUESTION_TEMPLATES.get(slot_name, f"请问{slot_name}是什么？")
        if suggestions:
            return f"{base}（可选：{' / '.join(suggestions[: self.MAX_SUGGESTIONS])}）"
        return base

    def _is_user_refusal(self, response: str) -> bool:
        response_lower = response.lower()
        return any(keyword in response_lower for keyword in self.REFUSAL_KEYWORDS)

    async def _handle_refusal(
        self, state: ClarificationState, user_response: str
    ) -> ClarificationResponse:
        if not state.pending_slot:
            return ClarificationResponse(
                response="好的，我们继续。", state=state, is_complete=False
            )

        for strategy in self.degradation_strategies:
            result = await strategy(state, state.pending_slot, user_response)
            if result:
                return result

        state.user_refused_slots.append(state.pending_slot)
        state.pending_slot = None
        return ClarificationResponse(
            response="好的，我们先跳过这个问题。", state=state, is_complete=False
        )

    async def _degradation_optional(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        if state.clarification_round <= 1:
            return ClarificationResponse(
                response="这个信息不是必须的，我们可以先跳过。您确定不需要提供吗？",
                state=state,
                is_complete=False,
            )
        return None

    async def _degradation_infer(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        if slot == "reason_category":
            state.collected_slots[slot] = "其他"
            state.pending_slot = None
            return ClarificationResponse(
                response="好的，我记为其他原因。", state=state, is_complete=False
            )
        return None

    async def _degradation_skip(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        state.user_refused_slots.append(slot)
        state.pending_slot = None
        return ClarificationResponse(response="好的，我们先继续。", state=state, is_complete=False)

    async def _degradation_escalate(
        self, state: ClarificationState, slot: str, response: str
    ) -> ClarificationResponse | None:
        return ClarificationResponse(
            response="这个问题比较复杂，我为您转接人工客服。",
            state=state,
            is_complete=True,
            collected_slots=state.collected_slots,
        )

    def _build_max_rounds_response(self, state: ClarificationState) -> ClarificationResponse:
        return ClarificationResponse(
            response="我已经了解了主要信息，现在就为您处理。",
            state=state,
            is_complete=True,
            collected_slots=state.collected_slots,
        )
