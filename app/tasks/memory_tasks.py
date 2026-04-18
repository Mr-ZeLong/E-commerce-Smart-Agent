"""
Memory extraction Celery tasks.
"""

import asyncio
import json
import logging
from typing import Any

from sqlmodel import Session, select

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_maker
from app.memory.extractor import FactExtractor
from app.memory.vector_manager import VectorMemoryManager
from app.models.memory import UserFact
from app.tasks.tracing_setup import setup_celery_langsmith_tracing

logger = logging.getLogger(__name__)


def _save_facts_body(
    self, user_id: int, thread_id: str, facts: list[dict[str, Any]], session: Session
) -> dict[str, Any]:
    try:
        saved_count = 0
        for fact_data in facts:
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
            return {"status": "failed", "message": "保存事实失败，已达到最大重试次数"}

    return {"status": "success", "facts_extracted": saved_count}


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
    session=None,
    extractor=None,
) -> dict[str, Any]:
    setup_celery_langsmith_tracing()

    history = json.loads(history_json)

    if extractor is None:
        extractor = FactExtractor()

    try:
        facts = asyncio.run(extractor.extract_facts(user_id, thread_id, history, answer, question))
    except Exception as exc:
        logger.exception("Fact extraction failed for user_id=%s thread_id=%s", user_id, thread_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "message": "事实提取失败，已达到最大重试次数"}

    if session is None:
        with sync_session_maker() as session:
            return _save_facts_body(self, user_id, thread_id, facts, session)
    return _save_facts_body(self, user_id, thread_id, facts, session)


@celery_app.task(name="memory.prune_vector_memory")
def prune_vector_memory() -> dict[str, Any]:
    manager = VectorMemoryManager()
    try:
        asyncio.run(manager.prune_old_messages(settings.MEMORY_RETENTION_DAYS))
        return {"status": "success", "pruned": True}
    except Exception:
        logger.exception("Vector memory pruning failed")
        return {"status": "failed", "message": "向量记忆清理失败"}
    finally:
        asyncio.run(manager.aclose())
