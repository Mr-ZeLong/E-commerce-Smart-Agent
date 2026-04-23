"""Review queue endpoints for admin API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.review import ReviewerMetrics
from app.services.review_queue import ReviewQueueService

router = APIRouter()
logger = logging.getLogger(__name__)


class ReviewTicketResponse(BaseModel):
    id: int
    conversation_id: str
    user_id: int
    risk_score: float
    risk_factors: dict[str, Any]
    status: str
    assigned_to: int | None
    created_at: str | None
    resolved_at: str | None
    sla_deadline: str | None
    resolution_action: str | None
    resolution_notes: str | None
    reviewer_accuracy: float | None
    confidence_score: float | None
    transfer_reason: str | None


class ReviewTicketListResponse(BaseModel):
    tickets: list[ReviewTicketResponse]
    total: int
    offset: int
    limit: int


class ReviewTicketActionRequest(BaseModel):
    action: str
    notes: str | None = None
    accuracy: float | None = None


class ReviewTicketAssignRequest(BaseModel):
    admin_id: int


class SLAMetricsResponse(BaseModel):
    total_resolved: int
    sla_met: int
    sla_compliance_rate: float
    pending_count: int
    at_risk_count: int
    avg_handling_time_minutes: float | None
    sla_target_hours: int


class ReviewerMetricsResponse(BaseModel):
    reviewer_id: int
    period_start: str
    period_end: str
    total_tickets: int
    avg_handling_time_minutes: float | None
    accuracy_score: float | None
    sla_compliance_rate: float


def _ticket_to_dict(ticket: Any) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "conversation_id": ticket.conversation_id,
        "user_id": ticket.user_id,
        "risk_score": ticket.risk_score,
        "risk_factors": ticket.risk_factors,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
        "resolution_action": ticket.resolution_action,
        "resolution_notes": ticket.resolution_notes,
        "reviewer_accuracy": ticket.reviewer_accuracy,
        "confidence_score": ticket.confidence_score,
        "transfer_reason": ticket.transfer_reason,
    }


@router.get("/", response_model=ReviewTicketListResponse)
async def list_review_tickets(
    status: str | None = None,
    min_risk: float | None = None,
    assigned_to: int | None = None,
    sla_at_risk: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    tickets, total = await service.list_tickets(
        status=status,
        min_risk=min_risk,
        assigned_to=assigned_to,
        sla_at_risk=sla_at_risk,
        offset=offset,
        limit=limit,
    )
    return {
        "tickets": [_ticket_to_dict(t) for t in tickets],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{ticket_id}", response_model=ReviewTicketResponse)
async def get_review_ticket(
    ticket_id: int,
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    ticket = await service.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return _ticket_to_dict(ticket)


@router.post("/{ticket_id}/assign")
async def assign_review_ticket(
    ticket_id: int,
    req: ReviewTicketAssignRequest,
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    try:
        ticket = await service.assign_ticket(ticket_id, req.admin_id)
        return _ticket_to_dict(ticket)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{ticket_id}/resolve")
async def resolve_review_ticket(
    ticket_id: int,
    req: ReviewTicketActionRequest,
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    try:
        ticket = await service.resolve_ticket(
            ticket_id, req.action, req.notes, req.accuracy
        )
        await service.update_reviewer_metrics(ticket.assigned_to or 0)
        return _ticket_to_dict(ticket)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{ticket_id}/escalate")
async def escalate_review_ticket(
    ticket_id: int,
    req: ReviewTicketActionRequest,
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    try:
        ticket = await service.escalate_ticket(ticket_id, req.notes)
        return _ticket_to_dict(ticket)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/metrics/sla", response_model=SLAMetricsResponse)
async def get_sla_metrics(
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    return await service.get_sla_metrics()


@router.get("/metrics/reviewer/{reviewer_id}", response_model=ReviewerMetricsResponse)
async def get_reviewer_metrics(
    reviewer_id: int,
    period_days: int = Query(7, ge=1, le=30),
    _: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = ReviewQueueService(session)
    await service.update_reviewer_metrics(reviewer_id, period_days=period_days)

    from sqlalchemy import select
    from app.models.review import ReviewerMetrics

    stmt = (
        select(ReviewerMetrics)  # type: ignore
        .where(ReviewerMetrics.reviewer_id == reviewer_id)  # type: ignore
        .order_by(ReviewerMetrics.period_start.desc())  # type: ignore
    )
    result = await session.exec(stmt)  # type: ignore
    metric = result.scalars().first()
    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metrics found for reviewer",
        )
    return {
        "reviewer_id": metric.reviewer_id,
        "period_start": metric.period_start.isoformat() if metric.period_start else "",
        "period_end": metric.period_end.isoformat() if metric.period_end else "",
        "total_tickets": metric.total_tickets,
        "avg_handling_time_minutes": metric.avg_handling_time_minutes,
        "accuracy_score": metric.accuracy_score,
        "sla_compliance_rate": metric.sla_compliance_rate,
    }
