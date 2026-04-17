import json

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.context.masking import mask_context_parts
from app.models.state import AgentProcessResult, AgentState
from app.tools.registry import ToolRegistry

PRODUCT_SYSTEM_PROMPT = """你是专业的商品查询助手。

规则：
1. 根据用户问题搜索商品目录，提供准确的商品信息
2. 如果用户询问具体参数且目录中有该参数，直接作答
3. 如果参数不在目录中，基于检索到的商品描述进行推理并明确说明
4. 严禁编造不存在的商品信息
5. 语气友好，帮助用户找到合适的商品"""


class ProductAgent(BaseAgent):
    def __init__(self, tool_registry: ToolRegistry, llm: BaseChatModel):
        super().__init__(name="product", llm=llm, system_prompt=PRODUCT_SYSTEM_PROMPT)
        self.tool_registry = tool_registry

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        tool_result = await self.tool_registry.execute("product", state)
        output = tool_result.output

        if output.get("status") == "not_found":
            response_text = "抱歉，未找到相关商品。请尝试使用其他关键词搜索。"
        elif output.get("direct_answer"):
            response_text = output["direct_answer"]
        else:
            products = output.get("products", [])
            if not products:
                response_text = "抱歉，未找到匹配的商品。"
            else:
                question = state.get("question", "")
                use_llm = self._should_use_llm(question)

                if use_llm:
                    context_parts = []
                    for p in products:
                        part = (
                            f"商品: {p.get('name', '未知商品')}, "
                            f"价格: ¥{p.get('price', 'N/A')}, "
                            f"库存: {'有货' if p.get('in_stock') else '缺货'}"
                        )
                        if p.get("description"):
                            part += f", 描述: {p['description']}"
                        if p.get("attributes"):
                            part += f", 参数: {json.dumps(p['attributes'], ensure_ascii=False)}"
                        context_parts.append(part)

                    context_parts = mask_context_parts(context_parts)

                    messages = self._create_messages(
                        question,
                        context={"context": context_parts},
                        memory_context=state.get("memory_context"),
                        user_context=self._build_user_context(state.get("memory_context")),
                        memory_context_config=state.get("memory_context_config"),
                    )
                    try:
                        response = await self._call_llm(messages, tags=["user_visible"])
                        response_text = response
                    except Exception:
                        response_text = self._format_product_list(products)
                else:
                    response_text = self._format_product_list(products)

        return {
            "response": response_text,
            "updated_state": {"product_data": output},
        }

    def _should_use_llm(self, question: str) -> bool:
        q = question.lower()
        attribute_keywords = [
            "屏幕",
            "刷新率",
            "hz",
            "电池",
            "相机",
            "重量",
            "尺寸",
            "内存",
            "存储",
            "颜色",
            "材质",
            "面料",
            "产地",
            "保修",
            "质保",
        ]
        question_patterns = ["多少", "多大", "什么", "怎么样", "吗", "?", "？"]
        has_attr = any(kw in q for kw in attribute_keywords)
        has_question = any(pw in q for pw in question_patterns)
        return has_attr or has_question

    def _format_product_list(self, products: list[dict]) -> str:
        lines = ["为您找到以下商品："]
        for p in products:
            lines.append(
                f"• {p.get('name', '未知商品')} "
                f"(价格: ¥{p.get('price', 'N/A')}, "
                f"库存: {'有货' if p.get('in_stock') else '缺货'})"
            )
            if p.get("description"):
                lines.append(f"  简介: {p['description'][:80]}...")
        return "\n".join(lines)
