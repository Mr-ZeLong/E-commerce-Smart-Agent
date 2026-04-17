"""Production monitoring dashboard endpoints for admin API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.observability import GraphExecutionLog

router = APIRouter()
logger = logging.getLogger(__name__)


class DashboardSummary(BaseModel):
    total_sessions_24h: int
    total_sessions_7d: int
    avg_confidence_24h: float | None
    transfer_rate_24h: float
    avg_latency_ms_24h: float | None
    containment_rate_24h: float
    token_efficiency_24h: float | None


class IntentAccuracyTrendItem(BaseModel):
    hour: str
    intent_category: str
    total: int
    correct: int
    accuracy: float


class RAGPrecisionItem(BaseModel):
    date: str
    avg_score: float
    count: int


class TransferReasonItem(BaseModel):
    reason: str
    count: int
    percentage: float


class TokenUsageItem(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class LatencyTrendItem(BaseModel):
    hour: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


class AlertItem(BaseModel):
    metric: str
    severity: str
    message: str
    value: float
    threshold: float


class MetricsDashboardResponse(BaseModel):
    summary: DashboardSummary
    intent_accuracy_trend: list[IntentAccuracyTrendItem]
    transfer_reasons: list[TransferReasonItem]
    token_usage: list[TokenUsageItem]
    latency_trend: list[LatencyTrendItem]
    alerts: list[AlertItem]


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    hours: int = Query(24, ge=1, le=720),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    since_7d = now - timedelta(days=7)

    total_result = await session.exec(
        select(func.count()).where(GraphExecutionLog.created_at >= since)
    )
    total = total_result.one() or 0

    total_7d_result = await session.exec(
        select(func.count()).where(GraphExecutionLog.created_at >= since_7d)
    )
    total_7d = total_7d_result.one() or 0

    avg_conf_result = await session.exec(
        select(func.avg(GraphExecutionLog.confidence_score)).where(
            GraphExecutionLog.created_at >= since,
            GraphExecutionLog.confidence_score.is_not(None),  # type: ignore
        )
    )
    avg_conf = avg_conf_result.one()

    transfer_count_result = await session.exec(
        select(func.count()).where(
            GraphExecutionLog.created_at >= since,
            GraphExecutionLog.needs_human_transfer.is_(True),  # type: ignore
        )
    )
    transfer_count = transfer_count_result.one() or 0
    transfer_rate = transfer_count / total if total > 0 else 0.0

    avg_latency_result = await session.exec(
        select(func.avg(GraphExecutionLog.total_latency_ms)).where(
            GraphExecutionLog.created_at >= since,
            GraphExecutionLog.total_latency_ms.is_not(None),  # type: ignore
        )
    )
    avg_latency = avg_latency_result.one()

    contained_count_result = await session.exec(
        select(func.count()).where(
            GraphExecutionLog.created_at >= since,
            GraphExecutionLog.needs_human_transfer.is_(False),  # type: ignore
        )
    )
    contained_count = contained_count_result.one() or 0
    containment_rate = contained_count / total if total > 0 else 0.0

    token_eff_result = await session.exec(
        select(func.avg(GraphExecutionLog.context_utilization)).where(
            GraphExecutionLog.created_at >= since,
            GraphExecutionLog.context_utilization.is_not(None),  # type: ignore
        )
    )
    token_eff = token_eff_result.one()

    return DashboardSummary(
        total_sessions_24h=total,
        total_sessions_7d=total_7d,
        avg_confidence_24h=round(float(avg_conf), 4) if avg_conf is not None else None,
        transfer_rate_24h=round(transfer_rate, 4),
        avg_latency_ms_24h=round(float(avg_latency), 2) if avg_latency is not None else None,
        containment_rate_24h=round(containment_rate, 4),
        token_efficiency_24h=round(float(token_eff), 4) if token_eff is not None else None,
    )


@router.get("/dashboard/intent-accuracy", response_model=list[IntentAccuracyTrendItem])
async def get_intent_accuracy_trend(
    hours: int = Query(24, ge=1, le=168),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.now(UTC) - timedelta(hours=hours)

    stmt = text(
        """
        SELECT
            date_trunc('hour', created_at) AS hour,
            intent_category,
            COUNT(*) AS total,
            SUM(CASE WHEN confidence_score >= 0.7 THEN 1 ELSE 0 END) AS correct
        FROM graph_execution_logs
        WHERE created_at >= :since
        GROUP BY date_trunc('hour', created_at), intent_category
        ORDER BY hour DESC
        """
    ).bindparams(since=since)

    result = await session.exec(stmt)  # type: ignore
    rows = result.mappings().all()

    return [
        IntentAccuracyTrendItem(
            hour=row["hour"].isoformat() if row["hour"] else "",
            intent_category=row["intent_category"] or "unknown",
            total=row["total"],
            correct=row["correct"],
            accuracy=round(row["correct"] / row["total"], 4) if row["total"] > 0 else 0.0,
        )
        for row in rows
    ]


@router.get("/dashboard/transfer-reasons", response_model=list[TransferReasonItem])
async def get_transfer_reasons(
    days: int = Query(7, ge=1, le=30),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.now(UTC) - timedelta(days=days)

    stmt = text(
        """
        SELECT
            intent_category AS reason,
            COUNT(*) AS count
        FROM graph_execution_logs
        WHERE created_at >= :since AND needs_human_transfer = TRUE
        GROUP BY intent_category
        ORDER BY count DESC
        """
    ).bindparams(since=since)

    result = await session.exec(stmt)  # type: ignore
    rows = result.mappings().all()

    total_transfers = sum(row["count"] for row in rows) or 1

    return [
        TransferReasonItem(
            reason=row["reason"] or "unknown",
            count=row["count"],
            percentage=round(row["count"] / total_transfers * 100, 2),
        )
        for row in rows
    ]


@router.get("/dashboard/token-usage", response_model=list[TokenUsageItem])
async def get_token_usage(
    days: int = Query(7, ge=1, le=30),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.now(UTC) - timedelta(days=days)

    stmt = text(
        """
        SELECT
            date_trunc('day', created_at) AS date,
            SUM(context_tokens) AS input_tokens,
            COUNT(*) * 150 AS estimated_output_tokens
        FROM graph_execution_logs
        WHERE created_at >= :since AND context_tokens IS NOT NULL
        GROUP BY date_trunc('day', created_at)
        ORDER BY date DESC
        """
    ).bindparams(since=since)

    result = await session.exec(stmt)  # type: ignore
    rows = result.mappings().all()

    return [
        TokenUsageItem(
            date=row["date"].isoformat() if row["date"] else "",
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["estimated_output_tokens"] or 0,
            total_tokens=(row["input_tokens"] or 0) + (row["estimated_output_tokens"] or 0),
        )
        for row in rows
    ]


@router.get("/dashboard/latency-trend", response_model=list[LatencyTrendItem])
async def get_latency_trend(
    hours: int = Query(24, ge=1, le=168),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.now(UTC) - timedelta(hours=hours)

    stmt = text(
        """
        SELECT
            date_trunc('hour', created_at) AS hour,
            AVG(total_latency_ms) AS avg_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_latency_ms) AS p95_latency_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_latency_ms) AS p99_latency_ms
        FROM graph_execution_logs
        WHERE created_at >= :since AND total_latency_ms IS NOT NULL
        GROUP BY date_trunc('hour', created_at)
        ORDER BY hour DESC
        """
    ).bindparams(since=since)

    result = await session.exec(stmt)  # type: ignore
    rows = result.mappings().all()

    return [
        LatencyTrendItem(
            hour=row["hour"].isoformat() if row["hour"] else "",
            avg_latency_ms=round(float(row["avg_latency_ms"]), 2) if row["avg_latency_ms"] else 0.0,
            p95_latency_ms=round(float(row["p95_latency_ms"]), 2) if row["p95_latency_ms"] else 0.0,
            p99_latency_ms=round(float(row["p99_latency_ms"]), 2) if row["p99_latency_ms"] else 0.0,
        )
        for row in rows
    ]


@router.get("/dashboard/rag-precision", response_model=list[RAGPrecisionItem])
async def get_rag_precision(
    days: int = Query(7, ge=1, le=30),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return RAG precision trend (proxy: confidence scores for POLICY intents)."""
    since = datetime.now(UTC) - timedelta(days=days)

    stmt = text(
        """
        SELECT
            date_trunc('day', created_at) AS date,
            AVG(confidence_score) AS avg_score,
            COUNT(*) AS count
        FROM graph_execution_logs
        WHERE created_at >= :since AND intent_category = 'POLICY' AND confidence_score IS NOT NULL
        GROUP BY date_trunc('day', created_at)
        ORDER BY date DESC
        """
    ).bindparams(since=since)

    result = await session.exec(stmt)  # type: ignore
    rows = result.mappings().all()

    return [
        RAGPrecisionItem(
            date=row["date"].isoformat() if row["date"] else "",
            avg_score=round(float(row["avg_score"]), 4) if row["avg_score"] else 0.0,
            count=row["count"],
        )
        for row in rows
    ]


class HallucinationRateItem(BaseModel):
    date: str
    hallucination_rate: float
    sampled_count: int


@router.get("/dashboard/hallucination-rate", response_model=list[HallucinationRateItem])
async def get_hallucination_rate(
    days: int = Query(7, ge=1, le=30),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return hallucination rate trend (proxy: low-confidence responses as potential hallucinations)."""
    since = datetime.now(UTC) - timedelta(days=days)

    stmt = text(
        """
        SELECT
            date_trunc('day', created_at) AS date,
            AVG(CASE WHEN confidence_score < 0.5 THEN 1.0 ELSE 0.0 END) AS hallucination_rate,
            COUNT(*) AS sampled_count
        FROM graph_execution_logs
        WHERE created_at >= :since AND confidence_score IS NOT NULL
        GROUP BY date_trunc('day', created_at)
        ORDER BY date DESC
        """
    ).bindparams(since=since)

    result = await session.exec(stmt)  # type: ignore
    rows = result.mappings().all()

    return [
        HallucinationRateItem(
            date=row["date"].isoformat() if row["date"] else "",
            hallucination_rate=round(float(row["hallucination_rate"]), 4)
            if row["hallucination_rate"]
            else 0.0,
            sampled_count=row["sampled_count"],
        )
        for row in rows
    ]


@router.get("/dashboard/alerts", response_model=list[AlertItem])
async def get_dashboard_alerts(
    hours: int = Query(24, ge=1, le=168),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    alerts: list[AlertItem] = []
    now = datetime.now(UTC)
    since_short = now - timedelta(hours=max(1, hours // 24))
    since_long = now - timedelta(hours=hours)

    transfer_rate_result = await session.exec(
        select(func.count()).where(
            GraphExecutionLog.created_at >= since_short,
            GraphExecutionLog.needs_human_transfer.is_(True),  # type: ignore
        )
    )
    transfer_count_short = transfer_rate_result.one() or 0

    total_short_result = await session.exec(
        select(func.count()).where(GraphExecutionLog.created_at >= since_short)
    )
    total_short = total_short_result.one() or 0

    if total_short > 0:
        transfer_rate = transfer_count_short / total_short
        if transfer_rate > settings.ALERT_TRANSFER_RATE_THRESHOLD:
            alerts.append(
                AlertItem(
                    metric="transfer_rate",
                    severity="high",
                    message=f"High transfer rate: {transfer_rate:.1%} in recent period",
                    value=round(transfer_rate, 4),
                    threshold=settings.ALERT_TRANSFER_RATE_THRESHOLD,
                )
            )

    avg_conf_result = await session.exec(
        select(func.avg(GraphExecutionLog.confidence_score)).where(
            GraphExecutionLog.created_at >= since_long,
            GraphExecutionLog.confidence_score.is_not(None),  # type: ignore
        )
    )
    avg_conf = avg_conf_result.one()
    if avg_conf is not None and avg_conf < settings.ALERT_CONFIDENCE_THRESHOLD:
        alerts.append(
            AlertItem(
                metric="avg_confidence",
                severity="medium",
                message=f"Low average confidence: {avg_conf:.2f} in last {hours}h",
                value=round(float(avg_conf), 4),
                threshold=settings.ALERT_CONFIDENCE_THRESHOLD,
            )
        )

    avg_latency_result = await session.exec(
        select(func.avg(GraphExecutionLog.total_latency_ms)).where(
            GraphExecutionLog.created_at >= since_short,
            GraphExecutionLog.total_latency_ms.is_not(None),  # type: ignore
        )
    )
    avg_latency = avg_latency_result.one()
    if avg_latency is not None and avg_latency > settings.ALERT_LATENCY_MS_THRESHOLD:
        alerts.append(
            AlertItem(
                metric="avg_latency",
                severity="medium",
                message=f"High average latency: {avg_latency:.0f}ms in recent period",
                value=round(float(avg_latency), 2),
                threshold=settings.ALERT_LATENCY_MS_THRESHOLD,
            )
        )

    return alerts
