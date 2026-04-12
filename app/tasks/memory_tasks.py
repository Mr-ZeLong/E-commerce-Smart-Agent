"""
Memory extraction Celery tasks.
"""

import asyncio
import json
import logging
from typing import Any

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_maker
from app.memory.extractor import FactExtractor
from app.memory.vector_manager import VectorMemoryManager
from app.models.memory import UserFact

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="memory.extract_and_save_facts",
    max_retries=2,
    default_retry_delay=60,
)
def extract_and_save_facts(
    self,
    user_id: int,
    thread_id: str,
    history_json: str,
    question: str,
    answer: str,
) -> dict[str, Any]:
    history = json.loads(history_json)

    extractor = FactExtractor()

    try:
        facts = asyncio.run(extractor.extract_facts(user_id, thread_id, history, answer, question))
    except Exception as exc:
        logger.exception("Fact extraction failed for user_id=%s thread_id=%s", user_id, thread_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "message": str(exc)}

    with sync_session_maker() as session:
        from sqlmodel import select

        try:
            saved_count = 0
            for fact_data in facts:
                # Deduplicate individual facts per thread instead of skipping the whole thread
                existing = session.exec(
                    select(UserFact)
                    .where(
                        UserFact.user_id == user_id,
                        UserFact.source_thread_id == thread_id,
                        UserFact.fact_type == fact_data["fact_type"],
                        UserFact.content == fact_data["content"],
                    )
                    .limit(1)
                ).one_or_none()
                if existing:
                    continue
                fact = UserFact(
                    user_id=user_id,
                    fact_type=fact_data["fact_type"],
                    content=fact_data["content"],
                    confidence=fact_data["confidence"],
                    source_thread_id=thread_id,
                )
                session.add(fact)
                saved_count += 1
            session.commit()
        except Exception as exc:
            logger.exception("Failed to save facts for user_id=%s thread_id=%s", user_id, thread_id)
            session.rollback()
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "message": str(exc)}

    return {"status": "success", "facts_extracted": saved_count}


@celery_app.task(name="memory.prune_vector_memory")
def prune_vector_memory() -> dict[str, Any]:
    manager = VectorMemoryManager()
    try:
        asyncio.run(manager.prune_old_messages(settings.MEMORY_RETENTION_DAYS))
        return {"status": "success", "pruned": True}
    except Exception as exc:
        logger.exception("Vector memory pruning failed")
        return {"status": "failed", "message": str(exc)}
    finally:
        asyncio.run(manager.aclose())
