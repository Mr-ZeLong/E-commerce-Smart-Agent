import asyncio
import logging
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlmodel import desc, func, select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.memory import AgentConfig, AgentConfigVersion
from app.models.observability import GraphExecutionLog
from app.models.prompt_effect_report import PromptEffectReport

logger = logging.getLogger(__name__)


async def _generate_single_report(session, agent_name: str, report_month: str) -> dict:
    start_dt = datetime.strptime(report_month, "%Y-%m").replace(tzinfo=UTC)
    end_dt = (start_dt + timedelta(days=32)).replace(day=1)

    version_result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_name == agent_name)
        .where(AgentConfigVersion.created_at <= end_dt)
        .order_by(desc(AgentConfigVersion.created_at))
        .limit(1)
    )
    version = version_result.one_or_none()
    version_id = version.id if version else None

    metrics_stmt = (
        select(
            func.count(sa.column("id")).label("total_sessions"),
            func.avg(sa.column("confidence_score")).label("avg_confidence"),
            func.sum(sa.case((sa.column("needs_human_transfer"), 1), else_=0)).label(
                "transfer_count"
            ),
            func.avg(sa.column("total_latency_ms")).label("avg_latency_ms"),
        )
        .select_from(GraphExecutionLog)
        .where(
            GraphExecutionLog.final_agent == agent_name,
            GraphExecutionLog.created_at >= start_dt,
            GraphExecutionLog.created_at < end_dt,
        )
    )
    result = await session.exec(metrics_stmt)
    row = result.one()

    total_sessions = int(row[0] or 0)
    avg_confidence = float(row[1]) if row[1] is not None else None
    transfer_count = int(row[2] or 0)
    avg_latency_ms = float(row[3]) if row[3] is not None else None
    transfer_rate = round(transfer_count / total_sessions, 4) if total_sessions > 0 else 0.0

    report = PromptEffectReport(
        report_month=report_month,
        agent_name=agent_name,
        version_id=version_id,
        total_sessions=total_sessions,
        avg_confidence=avg_confidence,
        transfer_rate=transfer_rate,
        avg_latency_ms=avg_latency_ms,
        key_changes="",
        recommendation="",
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    return {
        "report_id": report.id,
        "agent_name": agent_name,
        "report_month": report_month,
        "total_sessions": total_sessions,
        "transfer_rate": transfer_rate,
    }


async def _generate_monthly_report(
    agent_name: str | None = None, report_month: str | None = None
) -> dict:
    async with async_session_maker() as session:
        if agent_name and report_month:
            return await _generate_single_report(session, agent_name, report_month)

        target_month = report_month or (
            datetime.now(UTC).replace(day=1) - timedelta(days=1)
        ).strftime("%Y-%m")
        config_result = await session.exec(select(AgentConfig.agent_name))
        agent_names = list(config_result.all())
        results = []
        for name in agent_names:
            results.append(await _generate_single_report(session, name, target_month))
        return {"generated": len(results), "month": target_month, "reports": results}


@celery_app.task(bind=True, name="prompt_effect.generate_monthly_report")
def generate_monthly_report(
    _self, agent_name: str | None = None, report_month: str | None = None
) -> dict:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_generate_monthly_report(agent_name, report_month))
    finally:
        loop.close()
