from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings


def create_openai_llm(
    model: str | None = None,
    *,
    temperature: float = 0,
    timeout: float | None = None,
    max_retries: int | None = None,
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
    return ChatOpenAI(**llm_kwargs)


create_llm = create_openai_llm
