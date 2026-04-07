# app/graph/workflow.py
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from app.agents import SupervisorAgent
from app.core.config import settings
from app.graph.state import AgentState

app_graph = None

# 初始化 Supervisor Agent
supervisor = SupervisorAgent()


async def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 节点：协调所有 Agent

    这个节点替代了原来的 intent_router + retrieve/query_order/handle_refund
    """
    result = await supervisor.coordinate(state)
    return result


def route_after_evaluation(state: AgentState):
    """
    根据置信度评估结果路由

    - 需要人工接管 → END (等待审核)
    - 不需要 → 直接结束流程（Supervisor 已经生成了 answer）
    """
    if state.get("needs_human_transfer", False):
        print(f"[Workflow] 置信度不足 ({state.get('confidence_score', 0):.3f})，转人工")
        return END

    # 不需要转人工，流程结束
    return END


# 构建新的工作流
workflow = StateGraph(AgentState)

# 只保留 Supervisor 节点（它内部协调所有 Specialist Agents）
workflow.add_node("supervisor", supervisor_node)

# 入口 → Supervisor
workflow.add_edge(START, "supervisor")

# Supervisor 后根据评估结果路由
workflow.add_conditional_edges(
    "supervisor",
    route_after_evaluation,
    {END: END}
)


async def compile_app_graph():
    """编译 LangGraph"""
    print("🔧 Compiling Multi-Agent LangGraph with Redis checkpointer...")

    checkpointer = AsyncRedisSaver(redis_url=settings.REDIS_URL)
    await checkpointer.setup()

    compiled_graph = workflow.compile(checkpointer=checkpointer)

    print("✅ Multi-Agent LangGraph compiled successfully!")
    return compiled_graph
