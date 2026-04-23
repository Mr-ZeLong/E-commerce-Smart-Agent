import datetime
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import settings
from app.core.llm_factory import maybe_add_cache_control
from app.core.tracing import build_llm_config
from app.models.state import AgentProcessResult, AgentState

logger = logging.getLogger(__name__)

_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _estimate_tokens(text: str) -> int:
    """Estimate token count using a simple heuristic."""
    try:
        import tiktoken

        encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))
    except (ImportError, OSError):
        return len(text) // 4


def _truncate_parts_by_budget(parts: list[str], budget: int) -> list[str]:
    """Drop parts from the end until the estimated token count is within budget.

    The last part is always preserved (typically the user question).
    """
    if not parts:
        return parts
    while len(parts) > 1 and _estimate_tokens("\n".join(parts)) > budget:
        parts.pop(-2)
    return parts


DEFAULT_PROMPT_VARIABLES = {
    "company_name": "XX电商平台",
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
        self._few_shot_examples: list[dict[str, Any]] | None = None

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

    async def _get_few_shot_examples(self, query: str | None = None) -> list[dict[str, Any]] | None:
        if not self._few_shot_examples:
            return None
        if query is None or len(self._few_shot_examples) <= 3:
            return self._few_shot_examples
        from app.intent.few_shot_loader import select_top_k_examples_semantic

        return await select_top_k_examples_semantic(
            query, self._few_shot_examples, k=3, use_semantic=True
        )

    @abstractmethod
    async def process(self, state: AgentState) -> AgentProcessResult: ...

    def _extract_tracing_metadata(self, state: AgentState) -> dict[str, Any]:
        """Extract tracing metadata from AgentState."""
        metadata: dict[str, Any] = {}
        if user_id := state.get("user_id"):
            metadata["user_id"] = user_id
        if thread_id := state.get("thread_id"):
            metadata["thread_id"] = thread_id
        if intent_result := state.get("intent_result"):
            if isinstance(intent_result, dict):
                metadata["intent"] = intent_result.get("primary_intent")
            else:
                metadata["intent"] = getattr(intent_result, "primary_intent", None)
        if variant_model := state.get("variant_llm_model"):
            metadata["variant_llm_model"] = variant_model
        return metadata

    async def _call_llm(
        self,
        messages: list,
        temperature: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        try:
            llm = self.llm
            if metadata and metadata.get("variant_llm_model"):
                from app.core.llm_factory import create_openai_llm

                variant_model = metadata.get("variant_llm_model")
                llm = create_openai_llm(model=variant_model)
            llm = llm.bind(temperature=temperature) if temperature is not None else llm
            config = build_llm_config(
                agent_name=self.name,
                tags=tags,
                extra_metadata=metadata,
            )
            response = await llm.ainvoke(messages, config=config)
            content = str(response.content)

            from app.safety import OutputModerator

            moderator = OutputModerator(llm=self.llm)
            mod_result = await moderator.moderate(content, context=self.name)
            if not mod_result.is_safe and mod_result.replacement_text:
                return mod_result.replacement_text
            return content
        except (LangChainException, ConnectionError) as e:
            logger.error(f"[{self.name}] LLM call failed: {e}")
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
        memory_context_config: dict[str, Any] | None = None,
    ) -> str:
        """Build the user prompt, wrapping context and memory if provided."""
        if context or memory_context:
            return self._build_contextual_message(
                user_message, context or {}, memory_context, memory_context_config
            )
        return user_message

    def _build_history_messages(
        self,
        history: list[dict],
        budget: int,
    ) -> list[HumanMessage | AIMessage]:
        """Build history messages from most recent backwards within token budget.

        Args:
            history: List of message dicts with ``role`` and ``content`` keys.
            budget: Maximum token budget for history messages.

        Returns:
            List of ``HumanMessage`` / ``AIMessage`` objects to prepend before
            the current user message, ordered chronologically.
        """
        if not history or budget <= 0:
            return []
        result: list[HumanMessage | AIMessage] = []
        for msg in reversed(history):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role.lower() == "assistant":
                candidate_msg = AIMessage(content=content)
            else:
                candidate_msg = HumanMessage(content=content)
            candidate = [candidate_msg] + result
            total_tokens = _estimate_tokens("\n".join(str(m.content) for m in candidate))
            if total_tokens <= budget:
                result = candidate
            else:
                break
        return result

    def _create_messages(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        memory_context: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
        system_prompt_override: str | None = None,
        memory_context_config: dict[str, Any] | None = None,
        few_shot_examples: list[dict[str, Any]] | None = None,
        history: list[dict] | None = None,
    ) -> list:
        """Build message list with static system prompt and dynamic user content.

        System prompt is kept static to enable KV-cache hits across requests.
        Dynamic content (date, user-specific context) is moved to HumanMessage.
        """
        import hashlib

        messages: list[SystemMessage | HumanMessage | AIMessage] = []
        effective_prompt = (
            system_prompt_override
            if system_prompt_override is not None
            else (self._dynamic_system_prompt or self.system_prompt)
        )
        if effective_prompt:
            if system_prompt_override is not None:
                effective_prompt = render_prompt(effective_prompt, user_context or {})
            messages.append(SystemMessage(content=effective_prompt))

            prompt_hash = hashlib.md5(effective_prompt.encode()).hexdigest()
            logger.debug(f"[{self.name}] System prompt hash: {prompt_hash}")

        if history:
            history_budget = settings.HISTORY_CONTEXT_TOKEN_BUDGET
            if memory_context_config is not None:
                budget_override = memory_context_config.get("history_token_budget")
                if budget_override is not None:
                    history_budget = budget_override
            history_messages = self._build_history_messages(history, history_budget)
            messages.extend(history_messages)

        user_prompt = self._build_user_prompt(
            user_message, context, memory_context, memory_context_config
        )
        if few_shot_examples:
            from app.intent.few_shot_loader import format_agent_examples_for_prompt

            examples_text = format_agent_examples_for_prompt(self.name, few_shot_examples)
            if examples_text:
                user_prompt = examples_text + "\n" + user_prompt
        date_prefix = f"今天是 {datetime.date.today().isoformat()}。\n\n"
        messages.append(HumanMessage(content=date_prefix + user_prompt))
        return maybe_add_cache_control(messages)

    def _format_memory_prefix(
        self,
        memory_context: dict[str, Any] | None,
        memory_context_config: dict[str, Any] | None = None,
    ) -> str:
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
        if memory_context_config is not None:
            budget_override = memory_context_config.get("memory_token_budget")
            if budget_override is not None:
                budget = budget_override
            else:
                budget = settings.MEMORY_CONTEXT_TOKEN_BUDGET
        else:
            budget = settings.MEMORY_CONTEXT_TOKEN_BUDGET
        parts = _truncate_parts_by_budget(parts, budget)
        return "\n".join(parts)

    def _build_contextual_message(
        self,
        question: str,
        context: dict[str, Any],
        memory_context: dict[str, Any] | None = None,
        memory_context_config: dict[str, Any] | None = None,
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
        if memory_context_config is not None:
            budget_override = memory_context_config.get("memory_token_budget")
            if budget_override is not None:
                budget = budget_override
            else:
                budget = settings.MEMORY_CONTEXT_TOKEN_BUDGET
        else:
            budget = settings.MEMORY_CONTEXT_TOKEN_BUDGET
        parts = _truncate_parts_by_budget(parts, budget)
        return "\n".join(parts)
