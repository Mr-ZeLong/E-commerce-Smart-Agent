import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.models.complaint import ComplaintStatus, ComplaintTicket
from app.tasks.notifications import send_status_update

router = APIRouter()
logger = logging.getLogger(__name__)


class ComplaintTicketItem(BaseModel):
    id: int
    user_id: int
    thread_id: str
    category: str
    urgency: str
    status: str
    assigned_to: int | None
    created_at: str
    updated_at: str


class ComplaintListResponse(BaseModel):
    tickets: list[ComplaintTicketItem]
    total: int
    offset: int
    limit: int


class ComplaintDetailResponse(ComplaintTicketItem):
    order_sn: str | None
    description: str
    expected_resolution: str


class ComplaintAssignRequest(BaseModel):
    assigned_to: int


class ComplaintStatusRequest(BaseModel):
    status: str


class ComplaintResolveRequest(BaseModel):
    resolution_notes: str


@router.get("", response_model=ComplaintListResponse)
async def list_complaints(
    status: str | None = Query(None),
    urgency: str | None = Query(None),
    assigned_to: int | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    count_stmt = select(func.count()).select_from(ComplaintTicket)
    if status:
        count_stmt = count_stmt.where(ComplaintTicket.status == status)
    if urgency:
        count_stmt = count_stmt.where(ComplaintTicket.urgency == urgency)
    if assigned_to is not None:
        count_stmt = count_stmt.where(ComplaintTicket.assigned_to == assigned_to)
    total_result = await session.exec(count_stmt)
    total = total_result.one()

    stmt = select(ComplaintTicket).order_by(desc(ComplaintTicket.created_at))
    if status:
        stmt = stmt.where(ComplaintTicket.status == status)
    if urgency:
        stmt = stmt.where(ComplaintTicket.urgency == urgency)
    if assigned_to is not None:
        stmt = stmt.where(ComplaintTicket.assigned_to == assigned_to)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.exec(stmt)
    tickets = result.all()

    return ComplaintListResponse(
        tickets=[
            ComplaintTicketItem(
                id=cast(int, t.id),
                user_id=t.user_id,
                thread_id=t.thread_id,
                category=t.category,
                urgency=t.urgency,
                status=t.status,
                assigned_to=t.assigned_to,
                created_at=t.created_at.isoformat() if t.created_at else "",
                updated_at=t.updated_at.isoformat() if t.updated_at else "",
            )
            for t in tickets
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{ticket_id}", response_model=ComplaintDetailResponse)
async def get_complaint(
    ticket_id: int,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket_id))
    ticket = result.one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ComplaintDetailResponse(
        id=cast(int, ticket.id),
        user_id=ticket.user_id,
        thread_id=ticket.thread_id,
        category=ticket.category,
        urgency=ticket.urgency,
        status=ticket.status,
        assigned_to=ticket.assigned_to,
        order_sn=ticket.order_sn,
        description=ticket.description,
        expected_resolution=ticket.expected_resolution,
        created_at=ticket.created_at.isoformat() if ticket.created_at else "",
        updated_at=ticket.updated_at.isoformat() if ticket.updated_at else "",
    )


@router.patch("/{ticket_id}/assign")
async def assign_complaint(
    ticket_id: int,
    request: ComplaintAssignRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket_id))
    ticket = result.one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    ticket.assigned_to = request.assigned_to
    session.add(ticket)
    await session.commit()
    return {"success": True, "ticket_id": ticket_id, "assigned_to": request.assigned_to}


@router.patch("/{ticket_id}/status")
async def update_complaint_status(
    ticket_id: int,
    request: ComplaintStatusRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket_id))
    ticket = result.one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    old_status = ticket.status
    ticket.status = request.status
    session.add(ticket)
    await session.commit()

    if old_status != request.status and settings.ALERT_ADMIN_EMAILS:
        for email in settings.ALERT_ADMIN_EMAILS:
            send_status_update.delay(ticket_id, email)

    return {"success": True, "ticket_id": ticket_id, "status": request.status}


@router.patch("/{ticket_id}/resolve")
async def resolve_complaint(
    ticket_id: int,
    request: ComplaintResolveRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket_id))
    ticket = result.one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    ticket.status = ComplaintStatus.RESOLVED.value
    session.add(ticket)
    await session.commit()
    return {"success": True, "ticket_id": ticket_id, "resolution_notes": request.resolution_notes}
