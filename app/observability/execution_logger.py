from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.observability import GraphExecutionLog, GraphNodeLog
from app.observability.metrics import (
    record_chat_request,
    record_confidence_score,
    record_context_utilization,
    record_human_transfer,
    record_token_usage,
)


async def log_graph_execution(
    session: AsyncSession,
    thread_id: str,
    user_id: int,
    intent_category: str | None,
    final_agent: str | None,
    confidence_score: float | None,
    needs_human_transfer: bool,
    total_latency_ms: int | None,
    agent_config_version_id: int | None = None,
    context_tokens: int | None = None,
    context_utilization: float | None = None,
    langsmith_run_url: str | None = None,
    query: str | None = None,
) -> int:
    log = GraphExecutionLog(
        thread_id=thread_id,
        user_id=user_id,
        intent_category=intent_category,
        final_agent=final_agent,
        confidence_score=confidence_score,
        needs_human_transfer=needs_human_transfer,
        total_latency_ms=total_latency_ms,
        agent_config_version_id=agent_config_version_id,
        context_tokens=context_tokens,
        context_utilization=context_utilization,
        langsmith_run_url=langsmith_run_url,
        query=query,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    assert log.id is not None

    record_chat_request(intent_category=intent_category, final_agent=final_agent)
    if confidence_score is not None:
        record_confidence_score(float(confidence_score))
    if needs_human_transfer:
        record_human_transfer(reason="low_confidence")
    if context_utilization is not None:
        record_context_utilization(float(context_utilization))
    if context_tokens is not None:
        record_token_usage(tokens=int(context_tokens), agent=final_agent)

    return log.id


async def log_graph_node(
    session: AsyncSession,
    execution_id: int,
    node_name: str,
    latency_ms: int,
) -> None:
    log = GraphNodeLog(
        execution_id=execution_id,
        node_name=node_name,
        latency_ms=latency_ms,
    )
    session.add(log)
    await session.commit()
