from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings


def create_openai_llm(
    model: str | None = None,
    *,
    temperature: float = 0,
    timeout: float | None = None,
    max_retries: int | None = None,
    default_config: RunnableConfig | None = None,
    **kwargs,
) -> BaseChatModel:
    """Create a ChatOpenAI instance with project defaults."""
    llm_kwargs: dict = {
        "base_url": settings.OPENAI_BASE_URL,
        "api_key": SecretStr(settings.OPENAI_API_KEY),
        "model": model or settings.LLM_MODEL,
        "temperature": temperature,
        **kwargs,
    }
    if timeout is not None:
        llm_kwargs["timeout"] = timeout
    if max_retries is not None:
        llm_kwargs["max_retries"] = max_retries
    if "anthropic" in settings.OPENAI_BASE_URL.lower():
        llm_kwargs["extra_headers"] = {"anthropic-beta": "prompt-caching-2024-07-31"}

    llm = ChatOpenAI(**llm_kwargs)

    if default_config:
        llm = cast(BaseChatModel, llm.with_config(default_config))

    return llm


create_llm = create_openai_llm


def is_anthropic_endpoint() -> bool:
    """Return True if the configured LLM endpoint is Anthropic."""
    return "anthropic" in settings.OPENAI_BASE_URL.lower()


def maybe_add_cache_control(messages: list) -> list:
    """Add Anthropic cache_control to the last SystemMessage and last HumanMessage."""
    if not is_anthropic_endpoint():
        return messages
    last_system_idx = -1
    last_human_idx = -1
    for idx, msg in enumerate(messages):
        if isinstance(msg, SystemMessage):
            last_system_idx = idx
        elif isinstance(msg, HumanMessage):
            last_human_idx = idx

    result: list = []
    for idx, msg in enumerate(messages):
        if isinstance(msg, SystemMessage) and idx == last_system_idx:
            result.append(
                SystemMessage(
                    content=[
                        {
                            "type": "text",
                            "text": str(msg.content),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                )
            )
        elif isinstance(msg, HumanMessage) and idx == last_human_idx:
            result.append(
                HumanMessage(
                    content=[
                        {
                            "type": "text",
                            "text": str(msg.content),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                )
            )
        else:
            result.append(msg)
    return result
