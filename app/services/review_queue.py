from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.utils import utc_now
from app.models.review import ReviewerMetrics, ReviewStatus, ReviewTicket

logger = logging.getLogger(__name__)

SLA_HOURS = 4


class ReviewQueueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_ticket(
        self,
        conversation_id: str,
        user_id: int,
        risk_score: float,
        risk_factors: dict[str, Any] | None = None,
        last_messages: dict[str, Any] | None = None,
        confidence_score: float | None = None,
        transfer_reason: str | None = None,
    ) -> ReviewTicket:
        existing = await self.session.exec(
            select(ReviewTicket)
            .where(ReviewTicket.conversation_id == conversation_id)
            .where(
                ReviewTicket.status.in_([ReviewStatus.PENDING.value, ReviewStatus.ASSIGNED.value])
            )  # type: ignore
        )
        if existing.one_or_none() is not None:
            logger.info("Review ticket already exists for conversation %s", conversation_id)
            return existing.one()

        ticket = ReviewTicket(
            conversation_id=conversation_id,
            user_id=user_id,
            risk_score=risk_score,
            risk_factors=risk_factors or {},
            status=ReviewStatus.PENDING.value,
            sla_deadline=utc_now() + timedelta(hours=SLA_HOURS),
            last_messages=last_messages,
            confidence_score=confidence_score,
            transfer_reason=transfer_reason,
        )
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def assign_ticket(self, ticket_id: int, admin_id: int) -> ReviewTicket:
        result = await self.session.exec(select(ReviewTicket).where(ReviewTicket.id == ticket_id))
        ticket = result.one_or_none()
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id} not found")
        ticket.assigned_to = admin_id
        ticket.status = ReviewStatus.ASSIGNED.value
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def resolve_ticket(
        self, ticket_id: int, action: str, notes: str | None = None, accuracy: float | None = None
    ) -> ReviewTicket:
        result = await self.session.exec(select(ReviewTicket).where(ReviewTicket.id == ticket_id))
        ticket = result.one_or_none()
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id} not found")
        ticket.status = ReviewStatus.RESOLVED.value
        ticket.resolution_action = action
        ticket.resolution_notes = notes
        ticket.reviewer_accuracy = accuracy
        ticket.resolved_at = utc_now()
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def escalate_ticket(self, ticket_id: int, notes: str | None = None) -> ReviewTicket:
        result = await self.session.exec(select(ReviewTicket).where(ReviewTicket.id == ticket_id))
        ticket = result.one_or_none()
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id} not found")
        ticket.status = ReviewStatus.ESCALATED.value
        ticket.resolution_notes = notes
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def list_tickets(
        self,
        status: str | None = None,
        min_risk: float | None = None,
        assigned_to: int | None = None,
        sla_at_risk: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReviewTicket], int]:
        count_stmt = select(func.count()).select_from(ReviewTicket)
        stmt = select(ReviewTicket).order_by(desc(ReviewTicket.risk_score), ReviewTicket.created_at)  # type: ignore

        if status:
            count_stmt = count_stmt.where(ReviewTicket.status == status)
            stmt = stmt.where(ReviewTicket.status == status)
        if min_risk is not None:
            count_stmt = count_stmt.where(ReviewTicket.risk_score >= min_risk)  # type: ignore
            stmt = stmt.where(ReviewTicket.risk_score >= min_risk)  # type: ignore
        if assigned_to is not None:
            count_stmt = count_stmt.where(ReviewTicket.assigned_to == assigned_to)
            stmt = stmt.where(ReviewTicket.assigned_to == assigned_to)
        if sla_at_risk is True:
            deadline = utc_now() + timedelta(hours=1)
            count_stmt = count_stmt.where(ReviewTicket.sla_deadline <= deadline)  # type: ignore
            stmt = stmt.where(ReviewTicket.sla_deadline <= deadline)  # type: ignore

        total_result = await self.session.exec(count_stmt)
        total = total_result.one()

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.exec(stmt)
        return list(result.all()), total

    async def get_ticket(self, ticket_id: int) -> ReviewTicket | None:
        result = await self.session.exec(select(ReviewTicket).where(ReviewTicket.id == ticket_id))
        return result.one_or_none()

    async def get_sla_metrics(self) -> dict[str, Any]:
        now = utc_now()
        total_resolved_result = await self.session.exec(
            select(func.count()).where(ReviewTicket.status == ReviewStatus.RESOLVED.value)  # type: ignore
        )
        total_resolved = total_resolved_result.one() or 0

        sla_met_result = await self.session.exec(
            select(func.count()).where(
                ReviewTicket.status == ReviewStatus.RESOLVED.value,  # type: ignore
                ReviewTicket.resolved_at <= ReviewTicket.sla_deadline,  # type: ignore
            )
        )
        sla_met = sla_met_result.one() or 0

        pending_count_result = await self.session.exec(
            select(func.count()).where(
                ReviewTicket.status.in_([ReviewStatus.PENDING.value, ReviewStatus.ASSIGNED.value])  # type: ignore
            )
        )
        pending_count = pending_count_result.one() or 0

        at_risk_result = await self.session.exec(
            select(func.count()).where(
                ReviewTicket.status.in_([ReviewStatus.PENDING.value, ReviewStatus.ASSIGNED.value]),  # type: ignore
                ReviewTicket.sla_deadline <= now + timedelta(hours=1),  # type: ignore
            )
        )
        at_risk = at_risk_result.one() or 0

        avg_handling_result = await self.session.exec(
            select(
                func.avg(
                    func.extract("epoch", ReviewTicket.resolved_at - ReviewTicket.created_at) / 60  # type: ignore
                )
            ).where(ReviewTicket.status == ReviewStatus.RESOLVED.value)  # type: ignore
        )
        avg_handling = avg_handling_result.one()

        return {
            "total_resolved": total_resolved,
            "sla_met": sla_met,
            "sla_compliance_rate": round(sla_met / total_resolved, 4)
            if total_resolved > 0
            else 1.0,
            "pending_count": pending_count,
            "at_risk_count": at_risk,
            "avg_handling_time_minutes": round(float(avg_handling), 2) if avg_handling else None,
            "sla_target_hours": SLA_HOURS,
        }

    async def compute_risk_score(
        self,
        confidence: float | None,
        safety_blocked: bool,
        refund_amount: float | None,
        is_complaint: bool,
    ) -> tuple[float, dict[str, Any]]:
        score = 0.0
        factors: dict[str, Any] = {}

        if confidence is not None and confidence < 0.3:
            score += 0.4
            factors["low_confidence"] = confidence
        if safety_blocked:
            score += 0.3
            factors["safety_blocked"] = True
        if refund_amount is not None and refund_amount >= 2000.0:
            score += 0.2
            factors["high_refund"] = refund_amount
        if is_complaint:
            score += 0.1
            factors["complaint"] = True

        return min(score, 1.0), factors

    async def update_reviewer_metrics(self, reviewer_id: int, period_days: int = 7) -> None:
        now = utc_now()
        start = now - timedelta(days=period_days)

        result = await self.session.exec(
            select(
                func.count().label("total"),  # type: ignore
                func.avg(
                    func.extract("epoch", ReviewTicket.resolved_at - ReviewTicket.created_at) / 60  # type: ignore
                ).label("avg_time"),
                func.avg(ReviewTicket.reviewer_accuracy).label("avg_accuracy"),  # type: ignore
            )
            .where(ReviewTicket.assigned_to == reviewer_id)
            .where(ReviewTicket.status == ReviewStatus.RESOLVED.value)  # type: ignore
            .where(ReviewTicket.resolved_at >= start)  # type: ignore
        )
        row = result.one()

        sla_result = await self.session.exec(
            select(func.count()).where(
                ReviewTicket.assigned_to == reviewer_id,
                ReviewTicket.status == ReviewStatus.RESOLVED.value,  # type: ignore
                ReviewTicket.resolved_at <= ReviewTicket.sla_deadline,  # type: ignore
                ReviewTicket.resolved_at >= start,  # type: ignore
            )
        )
        sla_met = sla_result.one() or 0
        total = row.total or 0
        sla_rate = sla_met / total if total > 0 else 1.0

        existing = await self.session.exec(
            select(ReviewerMetrics)
            .where(ReviewerMetrics.reviewer_id == reviewer_id)
            .where(ReviewerMetrics.period_start == start)
        )
        metric = existing.one_or_none()
        if metric is None:
            metric = ReviewerMetrics(
                reviewer_id=reviewer_id,
                period_start=start,
                period_end=now,
            )

        metric.total_tickets = total
        metric.avg_handling_time_minutes = round(float(row.avg_time), 2) if row.avg_time else None
        metric.accuracy_score = round(float(row.avg_accuracy), 4) if row.avg_accuracy else None
        metric.sla_compliance_rate = round(sla_rate, 4)

        self.session.add(metric)
        await self.session.commit()
