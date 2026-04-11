import logging
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.llm_factory import create_openai_llm
from app.models.state import AgentState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(
        self,
        name: str,
        system_prompt: str | None = None,
        llm_model: str | None = None,
        llm: ChatOpenAI | None = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        if llm is not None:
            self.llm = llm
        else:
            self.llm = create_openai_llm(model=llm_model or settings.LLM_MODEL)

    @abstractmethod
    async def process(self, state: AgentState) -> dict[str, Any]:
        pass

    async def _call_llm(
        self, messages: list, temperature: float | None = None, tags: list[str] | None = None
    ) -> str:
        try:
            config: dict[str, Any] = {}
            if temperature is not None:
                config["temperature"] = temperature
            if tags:
                config["tags"] = tags

            if config:
                response = await self.llm.ainvoke(messages, config=config)  # type: ignore
            else:
                response = await self.llm.ainvoke(messages)
            return str(response.content)
        except Exception as e:
            logger.error(f"[{self.name}] LLM 调用失败: {e}")
            raise

    def _create_messages(self, user_message: str, context: dict | None = None) -> list:
        messages = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        if context:
            enhanced_message = self._build_contextual_message(user_message, context)
            messages.append(HumanMessage(content=enhanced_message))
        else:
            messages.append(HumanMessage(content=user_message))
        return messages

    def _build_contextual_message(self, question: str, context: dict) -> str:
        parts = []
        if context.get("context"):
            parts.append("[参考信息]:")
            for i, ctx in enumerate(context["context"], 1):
                parts.append(f"{i}. {ctx}")
            parts.append("")
        if context.get("order_data"):
            parts.append("[订单信息]:")
            order = context["order_data"]
            parts.append(f"订单号: {order.get('order_sn', 'N/A')}")
            parts.append(f"状态: {order.get('status', 'N/A')}")
            parts.append("")
        parts.append(f"[用户问题]:\n{question}")
        return "\n".join(parts)
