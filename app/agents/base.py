import datetime
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.state import AgentProcessResult, AgentState

logger = logging.getLogger(__name__)

_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

DEFAULT_PROMPT_VARIABLES = {
    "company_name": "XX电商平台",
    "current_date": lambda: datetime.date.today().isoformat(),
    "user_membership_level": "普通会员",
}


def _resolve_variable(value: Any) -> str:
    if callable(value):
        return str(value())
    return str(value)


def render_prompt(template: str, user_context: dict[str, Any]) -> str:
    """Render a prompt template by replacing {{variable}} placeholders."""
    variables = {**DEFAULT_PROMPT_VARIABLES, **user_context}
    resolved: dict[str, str] = {}
    for k, v in variables.items():
        resolved[k] = _resolve_variable(v)

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(resolved.get(key, match.group(0)))

    return _VARIABLE_PATTERN.sub(_replacer, template)


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

    async def _resolve_experiment_prompt(self, state: AgentState) -> str | None:
        """根据 AgentState 中的 experiment_variant_id 返回对应的覆盖 prompt."""
        from app.core.database import async_session_maker
        from app.models.experiment import ExperimentVariant

        variant_id = state.get("experiment_variant_id")
        if not variant_id:
            return None
        async with async_session_maker() as session:
            variant = await session.get(ExperimentVariant, variant_id)
            if variant and variant.system_prompt:
                return variant.system_prompt
        return None

    @abstractmethod
    async def process(self, state: AgentState) -> AgentProcessResult: ...

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

    def _build_user_context(self, memory_context: dict[str, Any] | None) -> dict[str, Any]:
        """Build user-specific template variables from memory context."""
        user_context: dict[str, Any] = {}
        if memory_context:
            user_profile = memory_context.get("user_profile") or {}
            membership_level = user_profile.get("membership_level")
            if membership_level:
                user_context["user_membership_level"] = membership_level
        return user_context

    def _build_system_prompt(self, user_context: dict[str, Any] | None = None) -> str | None:
        """Build the system prompt, applying template variable rendering."""
        effective_prompt = self._dynamic_system_prompt or self.system_prompt
        if not effective_prompt:
            return None
        return render_prompt(effective_prompt, user_context or {})

    def _build_user_prompt(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> str:
        """Build the user prompt, wrapping context and memory if provided."""
        if context or memory_context:
            return self._build_contextual_message(user_message, context or {}, memory_context)
        return user_message

    def _create_messages(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        memory_context: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
        system_prompt_override: str | None = None,
    ) -> list:
        messages = []
        system_prompt = (
            system_prompt_override
            if system_prompt_override is not None
            else self._build_system_prompt(user_context)
        )
        if system_prompt:
            if system_prompt_override is not None:
                system_prompt = render_prompt(system_prompt, user_context or {})
            messages.append(SystemMessage(content=system_prompt))
        user_prompt = self._build_user_prompt(user_message, context, memory_context)
        messages.append(HumanMessage(content=user_prompt))
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
