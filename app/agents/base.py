import logging
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.state import AgentProcessResult, AgentState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(
        self,
        name: str,
        llm: BaseChatModel,
        system_prompt: str | None = None,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self._dynamic_system_prompt: str | None = None

    async def _load_config(self) -> None:
        from app.agents.config_loader import get_effective_system_prompt

        self._dynamic_system_prompt = await get_effective_system_prompt(
            self.name, fallback=self.system_prompt
        )

    @abstractmethod
    async def process(self, state: AgentState) -> AgentProcessResult:
        pass

    async def _call_llm(
        self, messages: list, temperature: float | None = None, tags: list[str] | None = None
    ) -> str:
        try:
            llm = self.llm.bind(temperature=temperature) if temperature is not None else self.llm
            response = await llm.ainvoke(messages, config={"tags": tags} if tags else {})
            return str(response.content)
        except (LangChainException, ConnectionError) as e:
            logger.error(f"[{self.name}] LLM 调用失败: {e}")
            raise

    def _create_messages(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> list:
        messages = []
        effective_prompt = self._dynamic_system_prompt or self.system_prompt
        if effective_prompt:
            messages.append(SystemMessage(content=effective_prompt))
        if context or memory_context:
            enhanced_message = self._build_contextual_message(
                user_message, context or {}, memory_context
            )
            messages.append(HumanMessage(content=enhanced_message))
        else:
            messages.append(HumanMessage(content=user_message))
        return messages

    def _format_memory_prefix(self, memory_context: dict[str, Any] | None) -> str:
        if not memory_context:
            return ""
        parts = []
        interaction_summaries = memory_context.get("interaction_summaries") or []
        structured_facts = memory_context.get("structured_facts") or []
        user_profile = memory_context.get("user_profile") or {}
        relevant_past_messages = memory_context.get("relevant_past_messages") or []
        if interaction_summaries:
            parts.append("[过往会话摘要]")
            for idx, summary in enumerate(interaction_summaries, 1):
                text = summary.get("summary_text", "")
                intent = summary.get("resolved_intent")
                if intent:
                    parts.append(f"{idx}. [{intent}] {text}")
                else:
                    parts.append(f"{idx}. {text}")
            parts.append("")
        preferences = memory_context.get("preferences") or []
        if structured_facts or user_profile:
            parts.append("[User Context]")
            for fact in structured_facts:
                parts.append(f"- {fact.get('fact_type', 'Fact')}: {fact.get('content', '')}")
            for key, value in user_profile.items():
                parts.append(f"- {key}: {value}")
            parts.append("")
        if preferences:
            parts.append("[用户偏好]")
            for pref in preferences:
                parts.append(f"- {pref.get('preference_key')}: {pref.get('preference_value')}")
            parts.append("")
        if relevant_past_messages:
            parts.append("[来自你的历史对话]")
            for msg in relevant_past_messages:
                role = msg.get("role", "User")
                content = msg.get("content", "")
                display_role = "Assistant" if role.lower() == "assistant" else "User"
                parts.append(f"{display_role}: {content}")
            parts.append("")
        return "\n".join(parts)

    def _build_contextual_message(
        self,
        question: str,
        context: dict[str, Any],
        memory_context: dict[str, Any] | None = None,
    ) -> str:
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
        if memory_context:
            structured_facts = memory_context.get("structured_facts") or []
            user_profile = memory_context.get("user_profile") or {}
            relevant_past_messages = memory_context.get("relevant_past_messages") or []
            interaction_summaries = memory_context.get("interaction_summaries") or []
            if interaction_summaries:
                parts.append("[过往会话摘要]")
                for idx, summary in enumerate(interaction_summaries, 1):
                    text = summary.get("summary_text", "")
                    intent = summary.get("resolved_intent")
                    if intent:
                        parts.append(f"{idx}. [{intent}] {text}")
                    else:
                        parts.append(f"{idx}. {text}")
                parts.append("")
            preferences = memory_context.get("preferences") or []
            if structured_facts or user_profile:
                parts.append("[User Context]")
                for fact in structured_facts:
                    parts.append(f"- {fact.get('fact_type', 'Fact')}: {fact.get('content', '')}")
                for key, value in user_profile.items():
                    parts.append(f"- {key}: {value}")
                parts.append("")
            if preferences:
                parts.append("[用户偏好]")
                for pref in preferences:
                    parts.append(f"- {pref.get('preference_key')}: {pref.get('preference_value')}")
                parts.append("")
            if relevant_past_messages:
                parts.append("[来自你的历史对话]")
                for msg in relevant_past_messages:
                    role = msg.get("role", "User")
                    content = msg.get("content", "")
                    display_role = "Assistant" if role.lower() == "assistant" else "User"
                    parts.append(f"{display_role}: {content}")
                parts.append("")
        parts.append(f"[用户问题]:\n{question}")
        return "\n".join(parts)
