# app/graph/state.py
import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    # 基础信息
    question: str
    user_id: int

    # 意图标签:  "POLICY" 或 "ORDER" 或 "REFUND" 或 "OTHER"
    intent: str | None

    # 历史记录 (用于多轮对话)
    history:  Annotated[list[dict], operator.add]

    # 检索到的知识
    context:  list[str]

    # 查到的订单数据
    order_data: dict | None

    # v4.0 新增：会话 ID
    thread_id: str

    # v4.0 新增：审核状态
    audit_required: bool  # 是否需要人工审核
    audit_log_id: int | None  # 审计日志ID

    # v4.0 新增：结构化消息列表
    messages:  Annotated[list[dict[str, Any]], operator.add]

    # v3.0 保留：退货流程状态
    refund_flow_active: bool | None
    refund_order_sn: str | None
    refund_step: str | None

    # 最终回复
    answer: str
