# app/graph/workflow.py
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.graph.nodes import (
    check_refund_eligibility,
    generate,
    handle_refund,
    intent_router,
    query_order,
    retrieve,
)
from app.graph.state import AgentState

app_graph = None


# 1. 定义路由逻辑
def route_intent(state: AgentState):
    """意图路由"""
    intent = state.get("intent")
    if intent == "ORDER":
        return "query_order"
    elif intent == "POLICY":
        return "retrieve"
    elif intent == "REFUND":
        return "handle_refund"
    return "generate"


def route_after_refund(state: AgentState):
    """
    退货流程后的路由
    - 如果需要审核，直接结束（等待管理员）
    - 否则继续生成最终回复
    """
    if state.get("audit_required", False):
        # 需要人工审核，直接结束流程
        return END
    else:
        # 不需要审核，生成最终回复
        return "generate"


# 2. 构建图 (只定义结构，不编译)
workflow = StateGraph(AgentState)  # ty:ignore[invalid-argument-type]

# 添加所有节点
workflow.add_node("intent_router", intent_router)
workflow.add_node("retrieve", retrieve)
workflow.add_node("query_order", query_order)
workflow.add_node("handle_refund", handle_refund)
workflow.add_node("check_refund_eligibility", check_refund_eligibility)  # v4.0 新增审核节点
workflow.add_node("generate", generate)

# 设置入口
workflow.add_edge(START, "intent_router")

# 意图路由
workflow.add_conditional_edges(
    "intent_router",
    route_intent,
    {
        "query_order": "query_order",
        "retrieve": "retrieve",
        "handle_refund": "handle_refund",
        "generate": "generate"
    }
)

# 订单查询后 -> 生成回复
workflow.add_edge("query_order", "generate")

# 知识检索后 -> 生成回复
workflow.add_edge("retrieve", "generate")

# v4.0 关键修复：退货流程
# handle_refund -> check_refund_eligibility -> 根据审核结果路由
workflow.add_edge("handle_refund", "check_refund_eligibility")

workflow.add_conditional_edges(
    "check_refund_eligibility",
    route_after_refund,
    {
        "generate": "generate",
        END: END
    }
)

# 生成回复后结束
workflow.add_edge("generate", END)


async def compile_app_graph():
    """
    编译 LangGraph，初始化 Redis checkpointer
    """
    print("🔧 Compiling LangGraph with Redis checkpointer...")

    # 使用 Redis URL 创建 checkpointer（AsyncRedisSaver 接受 redis_url: str）
    checkpointer = AsyncRedisSaver(redis_url=settings.REDIS_URL)

    # 初始化 checkpointer（创建 RediSearch 索引）
    await checkpointer.setup()

    # 编译图
    compiled_graph = workflow.compile(checkpointer=checkpointer)

    print("✅ LangGraph compiled successfully!")
    return compiled_graph
