"""LangSmith tracing setup for Celery workers."""

import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_celery_langsmith_tracing() -> None:
    """Configure LangSmith environment variables for Celery workers.

    Must be called before any LLM instances are created in a Celery task.
    """
    if not settings.LANGSMITH_API_KEY or not settings.LANGSMITH_CELERY_TRACING:
        return

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY.get_secret_value())
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

    api_key = settings.LANGSMITH_API_KEY.get_secret_value()
    masked_key = f"{api_key[:8]}..." if len(api_key) > 8 else "***"
    logger.info(
        "LangSmith Celery tracing enabled (project=%s, api_key=%s)",
        settings.LANGSMITH_PROJECT,
        masked_key,
    )
