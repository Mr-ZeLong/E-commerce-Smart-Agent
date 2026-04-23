"""Tests for review queue admin endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.review import ReviewTicket
from app.models.user import User


async def create_admin_user() -> tuple[User, str]:
    unique = uuid.uuid4().hex[:8]
    username = f"admin_{unique}"
    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("adminpass"),
            email=f"{username}@_admin.com",
            full_name="Admin User",
            phone="13800138000",
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id or 0, is_admin=True)
        return user, token


async def create_sample_tickets(admin: User) -> list[ReviewTicket]:
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        tickets = [
            ReviewTicket(
                conversation_id=f"thread_{uuid.uuid4().hex[:8]}",
                user_id=admin.id or 1,
                risk_score=0.8,
                risk_factors={"low_confidence": True, "complaint": False},
                status="pending",
                assigned_to=None,
                created_at=now - timedelta(hours=2),
                sla_deadline=now + timedelta(hours=22),
                confidence_score=0.4,
                transfer_reason="low_confidence",
            ),
            ReviewTicket(
                conversation_id=f"thread_{uuid.uuid4().hex[:8]}",
                user_id=admin.id or 1,
                risk_score=0.3,
                risk_factors={"low_confidence": False, "complaint": False},
                status="pending",
                assigned_to=None,
                created_at=now - timedelta(hours=1),
                sla_deadline=now + timedelta(hours=23),
                confidence_score=0.7,
                transfer_reason=None,
            ),
            ReviewTicket(
                conversation_id=f"thread_{uuid.uuid4().hex[:8]}",
                user_id=admin.id or 1,
                risk_score=0.9,
                risk_factors={"low_confidence": True, "complaint": True},
                status="resolved",
                assigned_to=admin.id,
                created_at=now - timedelta(days=1),
                resolved_at=now - timedelta(hours=12),
                sla_deadline=now - timedelta(hours=10),
                resolution_action="approved_refund",
                resolution_notes="Approved full refund",
                reviewer_accuracy=0.95,
                confidence_score=0.2,
                transfer_reason="complaint",
            ),
        ]
        for ticket in tickets:
            session.add(ticket)
        await session.commit()
        for ticket in tickets:
            await session.refresh(ticket)
        return tickets


@pytest.mark.asyncio
async def test_list_review_tickets(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_tickets(admin)

    response = await client.get(
        "/api/v1/admin/review-queue/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["tickets"]) == 3


@pytest.mark.asyncio
async def test_list_review_tickets_filtered_by_status(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_tickets(admin)

    response = await client.get(
        "/api/v1/admin/review-queue/?status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for ticket in data["tickets"]:
        assert ticket["status"] == "pending"


@pytest.mark.asyncio
async def test_list_review_tickets_filtered_by_risk(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_tickets(admin)

    response = await client.get(
        "/api/v1/admin/review-queue/?min_risk=0.7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # Should include the 0.8 and 0.9 risk score tickets
    assert data["total"] == 2
    for ticket in data["tickets"]:
        assert ticket["risk_score"] >= 0.7


@pytest.mark.asyncio
async def test_get_review_ticket(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    tickets = await create_sample_tickets(admin)
    ticket_id = tickets[0].id

    response = await client.get(
        f"/api/v1/admin/review-queue/{ticket_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ticket_id
    assert data["conversation_id"] == tickets[0].conversation_id


@pytest.mark.asyncio
async def test_get_review_ticket_not_found(client: AsyncClient) -> None:
    admin, token = await create_admin_user()

    response = await client.get(
        "/api/v1/admin/review-queue/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_assign_review_ticket(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    tickets = await create_sample_tickets(admin)
    ticket_id = tickets[0].id

    response = await client.post(
        f"/api/v1/admin/review-queue/{ticket_id}/assign",
        json={"admin_id": admin.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assigned_to"] == admin.id
    assert data["status"] == "assigned"


@pytest.mark.asyncio
async def test_resolve_review_ticket(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    tickets = await create_sample_tickets(admin)
    # First assign the ticket
    ticket_id = tickets[0].id
    await client.post(
        f"/api/v1/admin/review-queue/{ticket_id}/assign",
        json={"admin_id": admin.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Then resolve it
    response = await client.post(
        f"/api/v1/admin/review-queue/{ticket_id}/resolve",
        json={"action": "approved", "notes": "Approved after review", "accuracy": 0.95},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolution_action"] == "approved"
    assert data["resolution_notes"] == "Approved after review"
    assert data["reviewer_accuracy"] == 0.95


@pytest.mark.asyncio
async def test_escalate_review_ticket(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    tickets = await create_sample_tickets(admin)
    ticket_id = tickets[1].id

    response = await client.post(
        f"/api/v1/admin/review-queue/{ticket_id}/escalate",
        json={"action": "escalate", "notes": "Needs senior review"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "escalated"


@pytest.mark.asyncio
async def test_sla_metrics(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_tickets(admin)

    response = await client.get(
        "/api/v1/admin/review-queue/metrics/sla",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_resolved" in data
    assert "sla_met" in data
    assert "sla_compliance_rate" in data
    assert "pending_count" in data


@pytest.mark.asyncio
async def test_reviewer_metrics(client: AsyncClient) -> None:
    admin, token = await create_admin_user()
    await create_sample_tickets(admin)

    # First resolve a ticket to generate metrics
    tickets = await create_sample_tickets(admin)
    ticket_id = tickets[0].id
    await client.post(
        f"/api/v1/admin/review-queue/{ticket_id}/assign",
        json={"admin_id": admin.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/admin/review-queue/{ticket_id}/resolve",
        json={"action": "approved", "notes": "Test", "accuracy": 0.9},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        f"/api/v1/admin/review-queue/metrics/reviewer/{admin.id}?period_days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reviewer_id"] == admin.id
    assert data["total_tickets"] >= 1
