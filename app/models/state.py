# app/models/state.py
import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict


@dataclass
class RetrievalResult:
    """统一封装检索结果"""

    chunks: list[str]
    similarities: list[float]
    sources: list[str]

    def to_dict(self) -> dict:
        return {
            "chunks": self.chunks,
            "similarities": self.similarities,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetrievalResult":
        return cls(
            chunks=data.get("chunks", []),
            similarities=data.get("similarities", []),
            sources=data.get("sources", []),
        )


class AgentState(TypedDict):
    """Agent 状态定义（v4.1 最终版）- 向后兼容设计"""

    # ========== 基础信息 ==========
    question: str
    user_id: int
    thread_id: str

    # ========== 意图与路由 ==========
    intent: str | None
    current_agent: str | None
    next_agent: str | None
    iteration_count: int
    retry_requested: bool

    # ========== 历史记录 ==========
    history: Annotated[list[dict], operator.add]

    # ========== RAG 检索结果（新旧双字段兼容）==========
    # 新字段：统一封装
    retrieval_result: RetrievalResult | None
    # 旧字段：向后兼容，从 retrieval_result.chunks 计算得出
    context: list[str]

    # ========== 订单数据 ==========
    order_data: dict | None

    # ========== 审核与人工接管（新旧双字段兼容）==========
    # 新字段：统一审核级别
    audit_level: str | None  # "none" | "auto" | "manual"
    # 旧字段：向后兼容，从 audit_level 计算得出
    audit_required: bool
    audit_type: str | None  # "RISK" | "CONFIDENCE" | None
    audit_log_id: int | None
    audit_reason: str | None

    # ========== 置信度评估（v4.1 新增）==========
    confidence_score: float | None
    confidence_signals: dict | None

    # ========== 生成结果 ==========
    messages: Annotated[list[dict[str, Any]], operator.add]
    answer: str

    # ========== 退货流程状态 ==========
    refund_flow_active: bool | None
    refund_order_sn: str | None
    refund_step: str | None


class AgentStatePartial(TypedDict, total=False):
    """Agent 状态部分定义，用于仅需填充部分字段的场景（如信号计算）"""

    question: str
    history: Annotated[list[dict], operator.add]
    retrieval_result: RetrievalResult | None


# ========== 状态转换工具函数 ==========


def normalize_state(state: dict) -> dict:
    """
    规范化状态，确保新旧字段一致性
    在每次状态更新后调用
    """
    # retrieval_result -> context
    if state.get("retrieval_result"):
        state["context"] = state["retrieval_result"].chunks
    else:
        state["context"] = state.get("context", [])

    # audit_level -> audit_required + audit_type
    audit_level = state.get("audit_level")
    if audit_level:
        state["audit_required"] = audit_level in ("auto", "manual")
        if audit_level == "manual":
            state["audit_type"] = state.get("audit_type") or "CONFIDENCE"
        else:
            state["audit_type"] = None
    else:
        # audit_required -> audit_level (旧代码兼容)
        if state.get("audit_required"):
            state["audit_level"] = state.get("audit_type", "manual").lower()
        else:
            state["audit_level"] = "none"

    return state


def get_audit_required(state: AgentState) -> bool:
    """向后兼容：从 audit_level 计算 audit_required"""
    return state.get("audit_level") in ("auto", "manual")


def get_audit_level_from_old(audit_required: bool, audit_type: str | None) -> str:
    """从旧字段计算新字段"""
    if not audit_required:
        return "none"
    if audit_type == "RISK":
        return "manual"  # 风险类必须人工审核
    return "auto"  # 其他自动审核
