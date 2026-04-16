from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.models.state import AgentProcessResult, AgentState
from app.tools.registry import ToolRegistry

PAYMENT_SYSTEM_PROMPT = """你是专业的电商支付助手。

规则：
1. 准确告知用户支付状态、发票信息、退款记录
2. 语气友好，数据清晰
3. 未查询到记录时给出积极引导"""


class PaymentAgent(BaseAgent):
    """支付专家 Agent"""

    def __init__(self, tool_registry: ToolRegistry, llm: BaseChatModel):
        super().__init__(name="payment", llm=llm, system_prompt=PAYMENT_SYSTEM_PROMPT)
        self.tool_registry = tool_registry

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        tool_result = await self.tool_registry.execute("payment", state)
        data = tool_result.output
        payment_status = data.get("payment_status", "未知")
        invoice_status = data.get("invoice_status", "未查询到发票信息")
        refund_records = data.get("refund_records", [])
        message = data.get("message", "")
        memory_prefix = self._format_memory_prefix(state.get("memory_context"))

        if message == "未查询到相关支付/退款记录" or not refund_records:
            response = (
                "未查询到相关支付/退款记录。\n"
                "您可以提供订单号以便我更准确地帮您查询，"
                "或前往‘我的订单’查看详细信息。"
            )
        else:
            lines = ["💳 支付/退款信息："]
            if payment_status != "未知":
                lines.append(f"支付状态: {payment_status}")
            if invoice_status != "未查询到发票信息":
                lines.append(f"发票状态: {invoice_status}")
            if refund_records:
                lines.append("退款记录:")
                for record in refund_records:
                    order_sn_text = (
                        f"订单号: {record.get('order_sn')}, " if record.get("order_sn") else ""
                    )
                    lines.append(
                        f"  - {order_sn_text}"
                        f"退款单号: {record.get('refund_id')}, "
                        f"金额: ¥{record.get('amount', 0)}, "
                        f"状态: {record.get('status', 'N/A')}"
                    )
            response = "\n".join(lines)

        if memory_prefix:
            response = memory_prefix + response

        return {
            "response": response,
            "updated_state": {"payment_data": data},
        }
