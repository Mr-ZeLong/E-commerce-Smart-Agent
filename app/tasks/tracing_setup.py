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
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

    masked_key = (
        f"{settings.LANGSMITH_API_KEY[:8]}..." if len(settings.LANGSMITH_API_KEY) > 8 else "***"
    )
    logger.info(
        "LangSmith Celery tracing enabled (project=%s, api_key=%s)",
        settings.LANGSMITH_PROJECT,
        masked_key,
    )
