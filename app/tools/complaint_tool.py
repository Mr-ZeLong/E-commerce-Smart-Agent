import logging
from typing import Any

from app.core.database import async_session_maker
from app.models.complaint import (
    ComplaintCategory,
    ComplaintStatus,
    ComplaintTicket,
    ComplaintUrgency,
    ExpectedResolution,
)
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ComplaintTool(BaseTool):
    name = "complaint"
    description = "Handle user complaints and create complaint tickets."

    async def execute(self, state: Any, **kwargs) -> ToolResult:
        _ = state
        _ = kwargs
        logger.debug("ComplaintTool.execute called")
        return ToolResult(output={"success": True})

    async def create_ticket(
        self,
        user_id: int,
        thread_id: str,
        category: str,
        urgency: str,
        description: str,
        expected_resolution: str,
        order_sn: str | None = None,
    ) -> dict[str, Any]:
        category = category.lower().strip()
        urgency = urgency.lower().strip()
        expected_resolution = expected_resolution.lower().strip()
        category = category.lower().strip()
        urgency = urgency.lower().strip()
        expected_resolution = expected_resolution.lower().strip()

        if category not in {c.value for c in ComplaintCategory}:
            category = ComplaintCategory.OTHER.value
        if urgency not in {u.value for u in ComplaintUrgency}:
            urgency = ComplaintUrgency.MEDIUM.value
        if expected_resolution not in {e.value for e in ExpectedResolution}:
            expected_resolution = ExpectedResolution.APOLOGY.value

        async with async_session_maker() as session:
            ticket = ComplaintTicket(
                user_id=user_id,
                thread_id=thread_id,
                category=category,
                urgency=urgency,
                description=description,
                expected_resolution=expected_resolution,
                order_sn=order_sn,
                status=ComplaintStatus.OPEN.value,
            )
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            logger.info("Created complaint ticket id=%s for user_id=%s", ticket.id, user_id)
            return {
                "ticket_id": ticket.id,
                "user_id": ticket.user_id,
                "thread_id": ticket.thread_id,
                "status": ticket.status,
            }
