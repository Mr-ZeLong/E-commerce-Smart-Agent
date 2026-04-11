import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.core.utils import build_thread_id
from app.models.audit import AuditAction, AuditLog, AuditTriggerType, RiskLevel
from app.models.message import MessageCard
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User


async def create_admin_user() -> tuple[User, str]:
    unique = uuid.uuid4().hex[:8]
    username = f"admin_{unique}"
    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("adminpass"),
            email=f"{username}@admin.com",
            full_name="Admin User",
            phone="13800138000",
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id, is_admin=True)
        return user, token


async def create_regular_user() -> User:
    unique = uuid.uuid4().hex[:8]
    username = f"user_{unique}"
    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("userpass"),
            email=f"{username}@user.com",
            full_name="Regular User",
            phone="13900139000",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        return user


async def create_order_and_refund(user: User) -> tuple[Order, RefundApplication]:
    async with async_session_maker() as session:
        assert user.id is not None
        order = Order(
            order_sn=f"ORD{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id,
            status=OrderStatus.DELIVERED,
            total_amount=199.99,
            items=[{"name": "Test Item", "price": 199.99}],
            shipping_address="Test Address",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        assert order.id is not None

        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            status=RefundStatus.PENDING,
            reason_detail="Test refund",
            refund_amount=199.99,
        )
        session.add(refund)
        await session.commit()
        await session.refresh(refund)
        assert refund.id is not None
        return order, refund


async def create_audit_log(
    user: User,
    order_id: int | None = None,
    refund_application_id: int | None = None,
    action: AuditAction = AuditAction.PENDING,
) -> AuditLog:
    async with async_session_maker() as session:
        assert user.id is not None
        thread_id = build_thread_id(user.id, f"test_thread_{uuid.uuid4().hex[:8]}")
        log = AuditLog(
            thread_id=thread_id,
            user_id=user.id,
            order_id=order_id,
            refund_application_id=refund_application_id,
            trigger_reason="Test audit",
            risk_level=RiskLevel.MEDIUM,
            action=action,
            trigger_type=AuditTriggerType.RISK,
            context_snapshot={},
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


@pytest.mark.asyncio
async def test_get_admin_tasks_returns_pending_tasks_for_admin(client):
    admin, token = await create_admin_user()
    user = await create_regular_user()
    order, refund = await create_order_and_refund(user)
    audit_log = await create_audit_log(user, order_id=order.id, refund_application_id=refund.id)

    response = await client.get(
        "/api/v1/admin/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    audit_ids = [task["audit_log_id"] for task in data]
    assert audit_log.id in audit_ids


@pytest.mark.asyncio
async def test_get_admin_tasks_rejects_non_admin_token(client):
    user = await create_regular_user()
    assert user.id is not None
    token = create_access_token(user_id=user.id, is_admin=False)

    response = await client.get(
        "/api/v1/admin/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Admin privileges required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_admin_tasks_rejects_missing_token(client):
    response = await client.get("/api/v1/admin/tasks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_admin_tasks_all_returns_stats(client):
    admin, token = await create_admin_user()
    user = await create_regular_user()
    order, refund = await create_order_and_refund(user)
    await create_audit_log(
        user, order_id=order.id, refund_application_id=refund.id, action=AuditAction.PENDING
    )

    response = await client.get(
        "/api/v1/admin/tasks-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "risk_tasks" in data
    assert "confidence_tasks" in data
    assert "manual_tasks" in data
    assert "total" in data
    assert data["total"] == data["risk_tasks"] + data["confidence_tasks"] + data["manual_tasks"]
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_admin_decision_approve_updates_all_records(client):
    admin, admin_token = await create_admin_user()
    user = await create_regular_user()
    order, refund = await create_order_and_refund(user)
    audit_log = await create_audit_log(
        user, order_id=order.id, refund_application_id=refund.id, action=AuditAction.PENDING
    )

    with (
        patch("app.services.admin_service.process_refund_payment") as mock_payment,
        patch("app.services.admin_service.send_refund_sms") as mock_sms,
        patch(
            "app.services.admin_service.manager.notify_status_change", new_callable=AsyncMock
        ) as mock_notify,
    ):
        response = await client.post(
            f"/api/v1/admin/resume/{audit_log.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"action": "APPROVE", "admin_comment": "Approved by test"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "APPROVE"

    async with async_session_maker() as session:
        result = await session.exec(select(AuditLog).where(AuditLog.id == audit_log.id))
        updated_log = result.one()
        assert updated_log.action == AuditAction.APPROVE
        assert updated_log.admin_id == admin.id
        assert updated_log.admin_comment == "Approved by test"
        assert updated_log.reviewed_at is not None

        result2 = await session.exec(
            select(RefundApplication).where(RefundApplication.id == refund.id)
        )
        updated_refund = result2.one()
        assert updated_refund.status == RefundStatus.APPROVED
        assert updated_refund.reviewed_by == admin.id

        result3 = await session.exec(
            select(MessageCard).where(
                MessageCard.thread_id == audit_log.thread_id,
                MessageCard.sender_id == admin.id,
            )
        )
        message = result3.one()
        assert message.content["action"] == "APPROVE"

    mock_payment.delay.assert_called_once()
    mock_sms.delay.assert_called_once()
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_decision_reject_updates_records(client):
    admin, admin_token = await create_admin_user()
    user = await create_regular_user()
    order, refund = await create_order_and_refund(user)
    audit_log = await create_audit_log(
        user, order_id=order.id, refund_application_id=refund.id, action=AuditAction.PENDING
    )

    with (
        patch("app.services.admin_service.process_refund_payment") as mock_payment,
        patch("app.services.admin_service.send_refund_sms") as mock_sms,
        patch(
            "app.services.admin_service.manager.notify_status_change", new_callable=AsyncMock
        ) as mock_notify,
    ):
        response = await client.post(
            f"/api/v1/admin/resume/{audit_log.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"action": "REJECT", "admin_comment": "Rejected by test"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "REJECT"

    async with async_session_maker() as session:
        result = await session.exec(select(AuditLog).where(AuditLog.id == audit_log.id))
        updated_log = result.one()
        assert updated_log.action == AuditAction.REJECT

        result2 = await session.exec(
            select(RefundApplication).where(RefundApplication.id == refund.id)
        )
        updated_refund = result2.one()
        assert updated_refund.status == RefundStatus.REJECTED

    mock_payment.delay.assert_not_called()
    mock_sms.delay.assert_not_called()
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_decision_returns_404_for_nonexistent_audit_log(client):
    admin, admin_token = await create_admin_user()

    response = await client.post(
        "/api/v1/admin/resume/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "APPROVE"},
    )
    assert response.status_code == 404
    assert "Audit log not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_decision_returns_400_for_already_processed_audit_log(client):
    admin, admin_token = await create_admin_user()
    user = await create_regular_user()
    order, refund = await create_order_and_refund(user)
    audit_log = await create_audit_log(
        user, order_id=order.id, refund_application_id=refund.id, action=AuditAction.APPROVE
    )

    response = await client.post(
        f"/api/v1/admin/resume/{audit_log.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "REJECT"},
    )
    assert response.status_code == 400
    assert "already been processed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_decision_rejects_non_admin_token(client):
    user = await create_regular_user()
    assert user.id is not None
    order, refund = await create_order_and_refund(user)
    audit_log = await create_audit_log(
        user, order_id=order.id, refund_application_id=refund.id, action=AuditAction.PENDING
    )
    token = create_access_token(user_id=user.id, is_admin=False)

    response = await client.post(
        f"/api/v1/admin/resume/{audit_log.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "APPROVE"},
    )
    assert response.status_code == 403
    assert "Admin privileges required" in response.json()["detail"]
