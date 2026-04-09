# app/graph/workflow.py
import logging

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from app.agents import SupervisorAgent
from app.core.config import settings
from app.models.state import AgentState

app_graph = None

_supervisor: SupervisorAgent | None = None

logger = logging.getLogger(__name__)


def get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor


async def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 节点：协调所有 Agent

    这个节点替代了原来的 intent_router + retrieve/query_order/handle_refund
    """
    try:
        supervisor = get_supervisor()
        result = await supervisor.coordinate(state)  # type: ignore
        return result
    except Exception as e:
        logger.error(f"[Workflow] Supervisor 节点错误: {e}")
        return {
            "answer": "抱歉，系统处理出现问题，请稍后重试或联系人工客服。",
            "needs_human_transfer": True,
            "transfer_reason": f"system_error: {str(e)}",
        }


def route_after_evaluation(state: AgentState):
    """
    根据置信度评估结果路由

    当前 Supervisor 节点已内部处理所有逻辑，流程统一结束。
    保留此路由函数以兼容 LangGraph 条件边接口。
    """
    if state.get("needs_human_transfer", False):
        logger.info(f"[Workflow] 置信度不足 ({state.get('confidence_score', 0):.3f})，转人工")
    return END


# 构建新的工作流
workflow = StateGraph(AgentState)  # type: ignore

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
    logger.info("🔧 Compiling Multi-Agent LangGraph with Redis checkpointer...")

    checkpointer = AsyncRedisSaver(redis_url=settings.REDIS_URL)
    await checkpointer.setup()

    compiled_graph = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Multi-Agent LangGraph compiled successfully!")
    return compiled_graph
