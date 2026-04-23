"""Celery tasks for post-chat observability to keep the SSE critical path fast."""

import logging
from typing import Any

from asgiref.sync import async_to_sync
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import desc, select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.memory import AgentConfigVersion
from app.models.observability import GraphExecutionLog, GraphNodeLog
from app.observability.metrics import (
    record_chat_latency,
    record_confidence_score,
    record_context_utilization,
    record_human_transfer,
    record_token_usage,
)
from app.observability.token_tracker import TokenTracker
from app.services.review_queue import ReviewQueueService

logger = logging.getLogger(__name__)


async def _async_log_chat_observability(
    thread_id: str,
    user_id: int,
    intent_category: str | None,
    final_state: dict[str, Any],
    node_latencies: dict[str, int],
    total_latency_ms: int,
    chat_request_question: str,
    variant_id: int | None,
    variant_llm_model: str | None,
    langsmith_run_url: str | None,
) -> int | None:
    """Async helper for observability logging using AsyncSession."""
    async with async_session_maker() as session:
        final_agent_name = final_state.get("current_agent")

        # Resolve agent config version
        version_id = None
        if final_agent_name:
            result = await session.exec(
                select(AgentConfigVersion)
                .where(AgentConfigVersion.agent_name == final_agent_name)
                .order_by(desc(AgentConfigVersion.created_at))
                .limit(1)
            )
            version = result.one_or_none()
            version_id = version.id if version else None

        # Log graph execution
        log = GraphExecutionLog(
            thread_id=thread_id,
            user_id=user_id,
            intent_category=intent_category,
            final_agent=final_agent_name,
            confidence_score=final_state.get("confidence_score"),
            needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
            total_latency_ms=total_latency_ms,
            agent_config_version_id=version_id,
            context_tokens=final_state.get("context_tokens"),
            context_utilization=final_state.get("context_utilization"),
            langsmith_run_url=langsmith_run_url,
            query=chat_request_question,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        execution_id = log.id
        assert execution_id is not None

        # Log per-node latencies
        for node_name, latency_ms in node_latencies.items():
            node_log = GraphNodeLog(
                execution_id=execution_id,
                node_name=node_name,
                latency_ms=latency_ms,
            )
            session.add(node_log)
        await session.commit()

        # Experiment metrics
        if variant_id is not None:
            try:
                from app.models.experiment import ExperimentMetrics

                metrics = ExperimentMetrics(
                    variant_id=variant_id,
                    user_id=user_id,
                    session_id=thread_id,
                    latency_ms=total_latency_ms,
                    token_count=final_state.get("context_tokens"),
                    confidence_score=final_state.get("confidence_score"),
                    needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
                )
                session.add(metrics)
                await session.commit()
            except SQLAlchemyError:
                logger.exception("Failed to record experiment metrics")
                await session.rollback()

        # Review ticket for high-risk conversations
        confidence = final_state.get("confidence_score")
        needs_transfer = final_state.get("needs_human_transfer", False)
        transfer_reason = final_state.get("transfer_reason")
        is_complaint = intent_category == "COMPLAINT"

        service = ReviewQueueService(session)
        risk_score, risk_factors = await service.compute_risk_score(
            confidence=confidence,
            safety_blocked=needs_transfer,
            refund_amount=None,
            is_complaint=is_complaint,
        )
        if risk_score >= 0.5:
            try:
                await service.create_ticket(
                    conversation_id=thread_id,
                    user_id=user_id,
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    confidence_score=confidence,
                    transfer_reason=transfer_reason,
                )
            except (SQLAlchemyError, OperationalError):
                logger.exception("Failed to create review ticket for thread %s", thread_id)

        if final_state.get("context_tokens") is not None:
            try:
                token_tracker = TokenTracker(session)
                response_text = final_state.get("answer", "")
                estimated_output_tokens = max(1, len(response_text) // 4)
                await token_tracker.log_usage(
                    user_id=user_id,
                    thread_id=thread_id,
                    agent_type=final_agent_name or "unknown",
                    input_tokens=int(final_state.get("context_tokens", 0)),
                    output_tokens=estimated_output_tokens,
                    query_text=chat_request_question,
                    model_name=variant_llm_model or "unknown",
                )
            except (SQLAlchemyError, OperationalError):
                logger.exception("Failed to log token usage to database")

    return execution_id


@celery_app.task(
    bind=True,
    name="observability.log_chat_observability",
    max_retries=2,
    default_retry_delay=30,
)
def log_chat_observability(
    self,
    thread_id: str,
    user_id: int,
    intent_category: str | None,
    final_state: dict[str, Any],
    node_latencies: dict[str, int],
    total_latency_ms: int,
    chat_request_question: str,
    variant_id: int | None,
    variant_llm_model: str | None,
    langsmith_run_url: str | None,
) -> dict[str, Any]:
    """Persist execution logs, metrics, review tickets, and token usage asynchronously.

    This task is enqueued from the chat endpoint after SSE streaming completes so
    that the HTTP response is not blocked by observability I/O.
    """
    try:
        execution_id = async_to_sync(_async_log_chat_observability)(
            thread_id=thread_id,
            user_id=user_id,
            intent_category=intent_category,
            final_state=final_state,
            node_latencies=node_latencies,
            total_latency_ms=total_latency_ms,
            chat_request_question=chat_request_question,
            variant_id=variant_id,
            variant_llm_model=variant_llm_model,
            langsmith_run_url=langsmith_run_url,
        )

        final_agent_name = final_state.get("current_agent")

        # Prometheus metrics (outside DB session)
        record_chat_latency(
            latency_seconds=total_latency_ms / 1000.0,
            final_agent=final_agent_name,
        )
        if final_state.get("confidence_score") is not None:
            record_confidence_score(float(final_state["confidence_score"]))
        if final_state.get("needs_human_transfer"):
            record_human_transfer(reason=final_state.get("transfer_reason") or "unknown")
        if final_state.get("context_utilization") is not None:
            record_context_utilization(float(final_state["context_utilization"]))
        if final_state.get("context_tokens") is not None:
            record_token_usage(
                tokens=int(final_state["context_tokens"]),
                agent=final_agent_name,
            )

        return {"status": "success", "execution_id": execution_id}
    except (SQLAlchemyError, OperationalError) as exc:
        logger.exception("Observability logging failed for thread %s", thread_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "message": "Observability logging max retries exceeded"}
