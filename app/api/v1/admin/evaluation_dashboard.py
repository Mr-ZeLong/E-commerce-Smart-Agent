"""Evaluation dashboard endpoints for shadow and adversarial testing."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.evaluation import AdversarialTestRun, ShadowTestResult

router = APIRouter()
logger = logging.getLogger(__name__)


class ShadowResultItem(BaseModel):
    id: int | None
    thread_id: str
    user_id: int
    query: str | None
    production_intent: str | None
    shadow_intent: str | None
    intent_match: bool
    jaccard_similarity: float
    semantic_similarity: float | None
    llm_quality_score: float | None
    production_latency_ms: int | None
    shadow_latency_ms: int | None
    latency_delta_ms: int | None
    latency_regression: bool
    created_at: datetime


class ShadowStatsResponse(BaseModel):
    total_comparisons: int
    intent_match_rate: float
    avg_jaccard_similarity: float | None
    avg_semantic_similarity: float | None
    avg_llm_quality_score: float | None
    avg_latency_delta_ms: float | None
    latency_regression_rate: float
    comparisons: list[ShadowResultItem]


class LatencyAlertItem(BaseModel):
    thread_id: str
    query: str | None
    latency_delta_ms: int | None
    threshold_ms: int
    severity: str


@router.get("/shadow/results", response_model=ShadowStatsResponse)
async def get_shadow_results(
    hours: int = Query(24, ge=1, le=720),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return shadow test results with statistics for the specified time window."""
    since = datetime.now(UTC) - timedelta(hours=hours)

    result = await session.exec(
        select(ShadowTestResult)
        .where(ShadowTestResult.created_at >= since)
        .order_by(desc(ShadowTestResult.created_at))
    )
    records: list[ShadowTestResult] = list(result.all())

    total = len(records)
    if total == 0:
        return ShadowStatsResponse(
            total_comparisons=0,
            intent_match_rate=0.0,
            avg_jaccard_similarity=None,
            avg_semantic_similarity=None,
            avg_llm_quality_score=None,
            avg_latency_delta_ms=None,
            latency_regression_rate=0.0,
            comparisons=[],
        )

    intent_matches = sum(1 for r in records if r.intent_match)
    jaccard_scores = [r.jaccard_similarity for r in records]
    semantic_scores = [r.semantic_similarity for r in records if r.semantic_similarity is not None]
    llm_scores = [r.llm_quality_score for r in records if r.llm_quality_score is not None]
    latency_deltas = [r.latency_delta_ms for r in records if r.latency_delta_ms is not None]
    regressions = sum(1 for r in records if r.latency_regression)

    return ShadowStatsResponse(
        total_comparisons=total,
        intent_match_rate=intent_matches / total,
        avg_jaccard_similarity=sum(jaccard_scores) / len(jaccard_scores),
        avg_semantic_similarity=(sum(semantic_scores) / len(semantic_scores))
        if semantic_scores
        else None,
        avg_llm_quality_score=(sum(llm_scores) / len(llm_scores)) if llm_scores else None,
        avg_latency_delta_ms=(sum(latency_deltas) / len(latency_deltas))
        if latency_deltas
        else None,
        latency_regression_rate=regressions / total,
        comparisons=[
            ShadowResultItem(
                id=r.id,
                thread_id=r.thread_id,
                user_id=r.user_id,
                query=r.query,
                production_intent=r.production_intent,
                shadow_intent=r.shadow_intent,
                intent_match=r.intent_match,
                jaccard_similarity=r.jaccard_similarity,
                semantic_similarity=r.semantic_similarity,
                llm_quality_score=r.llm_quality_score,
                production_latency_ms=r.production_latency_ms,
                shadow_latency_ms=r.shadow_latency_ms,
                latency_delta_ms=r.latency_delta_ms,
                latency_regression=r.latency_regression,
                created_at=r.created_at,
            )
            for r in records
        ],
    )


@router.get("/shadow/alerts", response_model=list[LatencyAlertItem])
async def get_shadow_latency_alerts(
    hours: int = Query(24, ge=1, le=168),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return shadow testing latency regression alerts."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    threshold = getattr(settings, "SHADOW_LATENCY_REGRESSION_THRESHOLD_MS", 500)

    result = await session.exec(
        select(ShadowTestResult)
        .where(ShadowTestResult.created_at >= since)
        .where(ShadowTestResult.latency_delta_ms.is_not(None))  # type: ignore
        .where(ShadowTestResult.latency_delta_ms > threshold)  # type: ignore
        .order_by(desc(ShadowTestResult.latency_delta_ms))
    )
    records: list[ShadowTestResult] = list(result.all())

    return [
        LatencyAlertItem(
            thread_id=r.thread_id,
            query=r.query,
            latency_delta_ms=r.latency_delta_ms,
            threshold_ms=threshold,
            severity="high" if (r.latency_delta_ms or 0) > threshold * 2 else "medium",
        )
        for r in records
    ]


class AdversarialRunItem(BaseModel):
    id: int | None
    run_date: date
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    triggered_by: str
    created_at: datetime


class AdversarialDashboardResponse(BaseModel):
    total_runs: int
    latest_pass_rate: float | None
    runs: list[AdversarialRunItem]


@router.get("/adversarial/runs", response_model=AdversarialDashboardResponse)
async def get_adversarial_runs(
    days: int = Query(30, ge=1, le=365),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return adversarial test suite execution history."""
    since = datetime.now(UTC) - timedelta(days=days)

    result = await session.exec(
        select(AdversarialTestRun)
        .where(AdversarialTestRun.created_at >= since)
        .order_by(desc(AdversarialTestRun.created_at))
    )
    records: list[AdversarialTestRun] = list(result.all())

    latest_pass_rate = records[0].pass_rate if records else None

    return AdversarialDashboardResponse(
        total_runs=len(records),
        latest_pass_rate=latest_pass_rate,
        runs=[
            AdversarialRunItem(
                id=r.id,
                run_date=r.run_date,
                total_cases=r.total_cases,
                passed_cases=r.passed_cases,
                failed_cases=r.failed_cases,
                pass_rate=r.pass_rate,
                triggered_by=r.triggered_by,
                created_at=r.created_at,
            )
            for r in records
        ],
    )


@router.post("/adversarial/trigger")
async def trigger_adversarial_run(
    _: int = Depends(get_admin_user_id),
) -> dict[str, Any]:
    """Trigger a manual adversarial test suite run."""
    from app.tasks.evaluation_tasks import run_adversarial_suite

    task = run_adversarial_suite.delay(triggered_by="manual")
    return {"task_id": task.id, "message": "Adversarial test suite triggered manually."}
