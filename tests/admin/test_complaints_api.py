import uuid

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.complaint import ComplaintStatus, ComplaintTicket, ComplaintUrgency
from tests.test_admin_api import create_admin_user, create_regular_user


async def create_complaint_ticket(
    user_id: int,
    category: str = "product_defect",
    status: str = ComplaintStatus.OPEN.value,
    urgency: str = ComplaintUrgency.MEDIUM.value,
    assigned_to: int | None = None,
) -> ComplaintTicket:
    async with async_session_maker() as session:
        ticket = ComplaintTicket(
            user_id=user_id,
            thread_id=f"thread_{uuid.uuid4().hex[:8]}",
            category=category,
            description="Test complaint description",
            expected_resolution="refund",
            status=status,
            urgency=urgency,
            assigned_to=assigned_to,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket


@pytest.mark.asyncio
async def test_list_complaints(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    ticket = await create_complaint_ticket(user.id or 0)

    response = await client.get(
        "/api/v1/admin/complaints",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tickets" in data
    assert data["total"] >= 1
    ticket_ids = [t["id"] for t in data["tickets"]]
    assert ticket.id in ticket_ids


@pytest.mark.asyncio
async def test_list_complaints_with_filters(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    await create_complaint_ticket(
        user.id or 0, status=ComplaintStatus.OPEN.value, urgency=ComplaintUrgency.HIGH.value
    )
    await create_complaint_ticket(
        user.id or 0, status=ComplaintStatus.IN_PROGRESS.value, urgency=ComplaintUrgency.LOW.value
    )

    response = await client.get(
        "/api/v1/admin/complaints?status=open&urgency=high",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(t["status"] == ComplaintStatus.OPEN.value for t in data["tickets"])
    assert all(t["urgency"] == ComplaintUrgency.HIGH.value for t in data["tickets"])


@pytest.mark.asyncio
async def test_list_complaints_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/complaints",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_complaint(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    ticket = await create_complaint_ticket(user.id or 0)

    response = await client.get(
        f"/api/v1/admin/complaints/{ticket.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ticket.id
    assert data["description"] == ticket.description


@pytest.mark.asyncio
async def test_get_complaint_not_found(client):
    _admin, token = await create_admin_user()

    response = await client.get(
        "/api/v1/admin/complaints/999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_complaint_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/complaints/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_assign_complaint(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    ticket = await create_complaint_ticket(user.id or 0)
    admin_user, _ = await create_admin_user()

    response = await client.patch(
        f"/api/v1/admin/complaints/{ticket.id}/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"assigned_to": admin_user.id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["assigned_to"] == admin_user.id

    async with async_session_maker() as session:
        result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket.id))
        updated = result.one()
        assert updated.assigned_to == admin_user.id


@pytest.mark.asyncio
async def test_assign_complaint_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.patch(
        "/api/v1/admin/complaints/1/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"assigned_to": 1},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_complaint_status(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    ticket = await create_complaint_ticket(user.id or 0, status=ComplaintStatus.OPEN.value)

    response = await client.patch(
        f"/api/v1/admin/complaints/{ticket.id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": ComplaintStatus.IN_PROGRESS.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == ComplaintStatus.IN_PROGRESS.value

    async with async_session_maker() as session:
        result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket.id))
        updated = result.one()
        assert updated.status == ComplaintStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_update_complaint_status_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.patch(
        "/api/v1/admin/complaints/1/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": ComplaintStatus.IN_PROGRESS.value},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_resolve_complaint(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    ticket = await create_complaint_ticket(user.id or 0, status=ComplaintStatus.IN_PROGRESS.value)

    response = await client.patch(
        f"/api/v1/admin/complaints/{ticket.id}/resolve",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolution_notes": "Resolved by refund"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    async with async_session_maker() as session:
        result = await session.exec(select(ComplaintTicket).where(ComplaintTicket.id == ticket.id))
        updated = result.one()
        assert updated.status == ComplaintStatus.RESOLVED.value


@pytest.mark.asyncio
async def test_resolve_complaint_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.patch(
        "/api/v1/admin/complaints/1/resolve",
        headers={"Authorization": f"Bearer {token}"},
        json={"resolution_notes": "Resolved"},
    )
    assert response.status_code == 403
