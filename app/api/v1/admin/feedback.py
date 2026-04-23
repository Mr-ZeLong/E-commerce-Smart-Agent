import csv
import io
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.services.online_eval import OnlineEvalService

router = APIRouter()
logger = logging.getLogger(__name__)
service = OnlineEvalService()


class QualityScoreRunRequest(BaseModel):
    sample_size: int = 50


@router.get("")
async def list_feedback(
    sentiment: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    agent_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_feedback(
        db=session,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
        agent_type=agent_type,
        category=category,
        search=search,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": f.id,
                "user_id": f.user_id,
                "thread_id": f.thread_id,
                "message_index": f.message_index,
                "score": f.score,
                "comment": f.comment,
                "category": f.category,
                "agent_type": f.agent_type,
                "confidence_score": f.confidence_score,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in items
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/export")
async def export_feedback(
    sentiment: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    agent_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    items, _ = await service.list_feedback(
        db=session,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
        agent_type=agent_type,
        category=category,
        search=search,
        offset=0,
        limit=10000,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "user_id",
            "thread_id",
            "message_index",
            "score",
            "comment",
            "category",
            "agent_type",
            "confidence_score",
            "created_at",
        ]
    )
    for f in items:
        writer.writerow(
            [
                f.id,
                f.user_id,
                f.thread_id,
                f.message_index,
                f.score,
                f.comment,
                f.category,
                f.agent_type,
                f.confidence_score,
                f.created_at.isoformat() if f.created_at else "",
            ]
        )
    return {
        "content": output.getvalue(),
        "filename": f"feedback_export_{datetime.now(UTC).isoformat()}.csv",
    }


@router.get("/csat")
async def get_csat_trend(
    days: int = Query(30, ge=1, le=365),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    trend = await service.get_csat_trend(db=session, days=days)
    return {"days": days, "trend": trend}


@router.get("/stats")
async def get_feedback_stats(
    days: int = Query(30, ge=1, le=365),
    agent_type: str | None = Query(None),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    stats = await service.get_feedback_stats(db=session, days=days, agent_type=agent_type)
    return {"days": days, **stats}


@router.post("/quality-score/run")
async def run_quality_score(
    request: QualityScoreRunRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    scores = await service.compute_quality_scores(db=session, sample_size=request.sample_size)
    return {"success": True, "scored_count": len(scores)}
