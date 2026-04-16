from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.observability import GraphExecutionLog, GraphNodeLog


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
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    assert log.id is not None
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
