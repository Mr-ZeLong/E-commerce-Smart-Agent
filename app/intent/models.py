"""意图识别数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IntentCategory(str, Enum):
    """一级意图：业务域"""

    ORDER = "ORDER"
    AFTER_SALES = "AFTER_SALES"
    POLICY = "POLICY"
    ACCOUNT = "ACCOUNT"
    PROMOTION = "PROMOTION"
    PAYMENT = "PAYMENT"
    LOGISTICS = "LOGISTICS"
    PRODUCT = "PRODUCT"
    RECOMMENDATION = "RECOMMENDATION"
    CART = "CART"
    COMPLAINT = "COMPLAINT"
    OTHER = "OTHER"


class IntentAction(str, Enum):
    """二级意图：动作类型"""

    QUERY = "QUERY"
    APPLY = "APPLY"
    MODIFY = "MODIFY"
    CANCEL = "CANCEL"
    CONSULT = "CONSULT"
    ADD = "ADD"
    REMOVE = "REMOVE"
    COMPARE = "COMPARE"


class SlotPriority(str, Enum):
    """槽位优先级"""

    P0 = "P0"  # 必须
    P1 = "P1"  # 重要
    P2 = "P2"  # 可选


@dataclass
class Slot:
    """槽位定义"""

    name: str
    description: str
    priority: SlotPriority
    required: bool = True
    extractor: str | None = None  # 提取器名称


@dataclass
class IntentResult:
    """意图识别结果"""

    primary_intent: IntentCategory
    secondary_intent: IntentAction
    tertiary_intent: str | None = None
    confidence: float = 0.0
    slots: dict[str, Any] | None = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    raw_query: str = ""

    def to_dict(self) -> dict:
        return {
            "primary_intent": self.primary_intent.value,
            "secondary_intent": self.secondary_intent.value,
            "tertiary_intent": self.tertiary_intent,
            "confidence": self.confidence,
            "slots": self.slots,
            "missing_slots": self.missing_slots,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "raw_query": self.raw_query,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IntentResult:
        return cls(
            primary_intent=IntentCategory(data["primary_intent"]),
            secondary_intent=IntentAction(data["secondary_intent"]),
            tertiary_intent=data.get("tertiary_intent"),
            confidence=data.get("confidence", 0.0),
            slots=data.get("slots", {}),
            missing_slots=data.get("missing_slots", []),
            needs_clarification=data.get("needs_clarification", False),
            clarification_question=data.get("clarification_question"),
            raw_query=data.get("raw_query", ""),
        )


@dataclass
class ClarificationState:
    """澄清状态"""

    session_id: str
    current_intent: IntentResult | None = None
    clarification_round: int = 0
    max_clarification_rounds: int = 3
    asked_slots: list[str] = field(default_factory=list)
    collected_slots: dict[str, Any] = field(default_factory=dict)
    pending_slot: str | None = None
    user_refused_slots: list[str] = field(default_factory=list)
    clarification_history: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def can_continue_clarification(self) -> bool:
        return self.clarification_round < self.max_clarification_rounds

    def increment_round(self):
        self.clarification_round += 1
        self.updated_at = datetime.now()
