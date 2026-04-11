from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.models.state import AgentProcessResult, AgentState
from app.tools.registry import ToolRegistry

LOGISTICS_SYSTEM_PROMPT = """你是专业的物流查询助手。

规则：
1. 根据订单号查询物流信息并清晰展示
2. 物流数据来自系统查询，严禁编造
3. 语气友好，解答用户疑问"""


class LogisticsAgent(BaseAgent):
    def __init__(self, tool_registry: ToolRegistry, llm: BaseChatModel):
        super().__init__(name="logistics", llm=llm, system_prompt=LOGISTICS_SYSTEM_PROMPT)
        self.tool_registry = tool_registry

    async def process(self, state: AgentState) -> AgentProcessResult:
        tool_result = await self.tool_registry.execute("logistics", state)
        output = tool_result.output

        if output.get("status") == "未找到订单":
            response_text = "抱歉，未找到相关订单的物流信息。请确认订单号是否正确。"
        else:
            response_text = (
                f"📦 物流信息：\n"
                f"物流单号: {output.get('tracking_number', '暂无')}\n"
                f"承运商: {output.get('carrier', 'N/A')}\n"
                f"状态: {output.get('status', 'N/A')}\n"
                f"最新动态: {output.get('latest_update', '暂无')}\n"
                f"预计送达: {output.get('estimated_delivery', '暂无')}"
            )

        return {"response": response_text, "updated_state": {"order_data": output}}
