import logging
from datetime import datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.observability import GraphExecutionLog
from app.services.online_eval import OnlineEvalService

router = APIRouter()
logger = logging.getLogger(__name__)
service = OnlineEvalService()


class CsatTrendItem(BaseModel):
    date: str
    avg_score: float
    count: int


class RootCauseItem(BaseModel):
    category: str
    count: int


class AgentComparisonItem(BaseModel):
    final_agent: str
    total_sessions: int
    avg_confidence: float | None
    transfer_rate: float
    avg_latency_ms: float | None
    complaint_count: int


class TraceItem(BaseModel):
    id: int
    thread_id: str
    user_id: int
    intent_category: str | None
    final_agent: str | None
    confidence_score: float | None
    needs_human_transfer: bool
    langsmith_run_url: str | None
    created_at: str
    total_latency_ms: int | None


class TraceListResponse(BaseModel):
    traces: list[TraceItem]
    total: int
    offset: int
    limit: int


@router.get("/csat", response_model=list[CsatTrendItem])
async def get_csat_trend(
    days: int = Query(30, ge=1, le=365),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    data = await service.get_csat_trend(db=session, days=days)
    return [
        CsatTrendItem(
            date=item["date"],
            avg_score=item["csat"],
            count=item["thumbs_up"] + item["thumbs_down"],
        )
        for item in data
    ]


@router.get("/complaint-root-causes", response_model=list[RootCauseItem])
async def get_complaint_root_causes(
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        text(
            """
            SELECT category, COUNT(*) as cnt
            FROM complaint_tickets
            GROUP BY category
            ORDER BY cnt DESC
            """
        )
    )
    rows = result.mappings().all()
    return [RootCauseItem(category=r["category"], count=r["cnt"]) for r in rows]


@router.get("/agent-comparison", response_model=list[AgentComparisonItem])
async def get_agent_comparison(
    days: int = Query(30, ge=1, le=365),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.utcnow() - timedelta(days=days)

    stmt = text(
        """
        SELECT
            final_agent,
            COUNT(*) AS total_sessions,
            AVG(confidence_score) AS avg_confidence,
            SUM(CASE WHEN needs_human_transfer THEN 1 ELSE 0 END) AS transfer_count,
            AVG(total_latency_ms) AS avg_latency_ms
        FROM graph_execution_logs
        WHERE created_at >= :since
        GROUP BY final_agent
        """
    ).bindparams(since=since)
    result = await session.execute(stmt)
    rows = result.mappings().all()

    complaint_stmt = text(
        """
        SELECT final_agent, COUNT(*) AS complaint_count
        FROM graph_execution_logs
        WHERE created_at >= :since AND intent_category = 'COMPLAINT'
        GROUP BY final_agent
        """
    ).bindparams(since=since)
    complaint_result = await session.execute(complaint_stmt)
    complaint_map = {
        r["final_agent"]: r["complaint_count"] for r in complaint_result.mappings().all()
    }

    out: list[AgentComparisonItem] = []
    for row in rows:
        agent_name = row["final_agent"]
        total = row["total_sessions"] or 0
        avg_conf = float(row["avg_confidence"]) if row["avg_confidence"] is not None else None
        transfers = int(row["transfer_count"] or 0)
        avg_latency = float(row["avg_latency_ms"]) if row["avg_latency_ms"] is not None else None
        out.append(
            AgentComparisonItem(
                final_agent=agent_name or "unknown",
                total_sessions=total,
                avg_confidence=round(avg_conf, 4) if avg_conf is not None else None,
                transfer_rate=round(transfers / total, 4) if total else 0.0,
                avg_latency_ms=round(avg_latency, 2) if avg_latency is not None else None,
                complaint_count=complaint_map.get(agent_name or "", 0),
            )
        )
    return out


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    days: int = Query(7, ge=1, le=90),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.utcnow() - timedelta(days=days)

    count_stmt = (
        select(func.count())
        .select_from(GraphExecutionLog)
        .where(GraphExecutionLog.created_at >= since)
    )
    total_result = await session.exec(count_stmt)
    total = total_result.one()

    stmt = (
        select(GraphExecutionLog)
        .where(GraphExecutionLog.created_at >= since)
        .order_by(desc(GraphExecutionLog.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    logs = result.all()

    return TraceListResponse(
        traces=[
            TraceItem(
                id=cast(int, log.id),
                thread_id=log.thread_id,
                user_id=log.user_id,
                intent_category=log.intent_category,
                final_agent=log.final_agent,
                confidence_score=log.confidence_score,
                needs_human_transfer=log.needs_human_transfer,
                langsmith_run_url=log.langsmith_run_url,
                created_at=log.created_at.isoformat() if log.created_at else "",
                total_latency_ms=log.total_latency_ms,
            )
            for log in logs
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
