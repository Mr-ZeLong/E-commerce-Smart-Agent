"""Token usage monitoring endpoints for admin API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.observability.token_tracker import TokenTracker

router = APIRouter()
logger = logging.getLogger(__name__)


class TokenUsageSummaryResponse(BaseModel):
    period_days: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    query_count: int
    unique_users: int


class TokenUsageByUserResponse(BaseModel):
    user_id: int
    period_days: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    query_count: int


class TokenUsageByAgentResponse(BaseModel):
    agent_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    query_count: int


class HighCostQueryResponse(BaseModel):
    id: int
    user_id: int
    thread_id: str
    agent_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    query_text: str | None
    created_at: str


class SuggestionResponse(BaseModel):
    id: int
    user_id: int | None
    thread_id: str | None
    suggestion_type: str
    message: str
    status: str
    created_at: str | None


@router.get("/", response_model=TokenUsageSummaryResponse)
async def get_token_usage_summary(
    days: int = Query(7, ge=1, le=90),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tracker = TokenTracker(session)
    return await tracker.get_overall_usage(days=days)


@router.get("/by-user/")
async def get_token_usage_by_user(
    user_id: int = Query(..., description="User ID to query"),
    days: int = Query(7, ge=1, le=90),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    tracker = TokenTracker(session)
    daily = await tracker.get_user_daily_aggregate(user_id)
    period = await tracker.get_user_period_aggregate(user_id, days=days)
    return [daily, period]


@router.get("/by-agent/")
async def get_token_usage_by_agent(
    days: int = Query(7, ge=1, le=90),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    tracker = TokenTracker(session)
    return await tracker.get_agent_aggregate(days=days)


@router.get("/high-cost/")
async def get_high_cost_queries(
    threshold: int = Query(10000, ge=1000),
    limit: int = Query(50, ge=1, le=200),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    tracker = TokenTracker(session)
    return await tracker.get_high_cost_queries(threshold=threshold, limit=limit)


@router.get("/anomalies/")
async def get_token_anomalies(
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    tracker = TokenTracker(session)
    return await tracker.check_anomalies()


@router.get("/suggestions/", response_model=list[SuggestionResponse])
async def get_optimization_suggestions(
    user_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    tracker = TokenTracker(session)
    suggestions = await tracker.get_suggestions(user_id=user_id, status=status, limit=limit)
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "thread_id": s.thread_id,
            "suggestion_type": s.suggestion_type,
            "message": s.message,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in suggestions
    ]
