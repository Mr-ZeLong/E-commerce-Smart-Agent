from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.models.state import AgentProcessResult, AgentState
from app.tools.registry import ToolRegistry

CART_SYSTEM_PROMPT = """你是专业的购物车助手。

规则：
1. 帮助用户查看购物车、添加商品、移除商品或修改数量
2. 操作完成后清晰告知用户购物车当前状态
3. 如果商品不存在或操作失败，明确说明原因
4. 语气友好，积极引导用户完成购买"""


class CartAgent(BaseAgent):
    def __init__(self, tool_registry: ToolRegistry, llm: BaseChatModel):
        super().__init__(name="cart", llm=llm, system_prompt=CART_SYSTEM_PROMPT)
        self.tool_registry = tool_registry

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        tool_result = await self.tool_registry.execute("cart", state)
        output = tool_result.output
        memory_prefix = self._format_memory_prefix(state.get("memory_context"))

        action = output.get("action")
        status = output.get("status")

        if status == "error":
            response_text = f"操作失败：{output.get('reason', '未知错误')}"
        elif action == "QUERY":
            items = output.get("items", [])
            total = output.get("total", 0.0)
            if not items:
                response_text = "您的购物车是空的，快去挑选心仪的商品吧！"
            else:
                lines = [f"🛒 购物车（共 {len(items)} 件商品，合计 ¥{total}）："]
                for item in items:
                    lines.append(
                        f"• {item.get('name', item.get('product_id', '未知商品'))} "
                        f"x {item.get('quantity', 1)} = ¥{item.get('subtotal', 0)}"
                    )
                response_text = "\n".join(lines)
        elif action == "ADD":
            response_text = (
                f"已将 {output.get('name', output.get('product_id', '商品'))} "
                f"加入购物车，数量 {output.get('quantity', 1)}。"
            )
        elif action == "REMOVE":
            response_text = f"已移除商品 {output.get('name', output.get('product_id', ''))}。"
        elif action == "MODIFY":
            response_text = (
                f"已将 {output.get('name', output.get('product_id', '商品'))} "
                f"数量修改为 {output.get('quantity', 1)}。"
            )
        else:
            response_text = "购物车操作已完成。"

        if memory_prefix:
            response_text = memory_prefix + response_text

        return {
            "response": response_text,
            "updated_state": {"cart_data": output},
        }
