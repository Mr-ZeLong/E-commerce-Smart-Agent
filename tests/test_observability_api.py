import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.core.utils import utc_now
from app.models.observability import GraphExecutionLog, GraphNodeLog
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


async def seed_logs() -> None:
    async with async_session_maker() as session:
        await session.execute(  # type: ignore
            text(
                "DELETE FROM graph_node_logs WHERE execution_id IN (SELECT id FROM graph_execution_logs)"
            )
        )
        await session.execute(text("DELETE FROM graph_execution_logs"))  # type: ignore
        for uid in (1, 2, 3):
            await session.execute(
                text(
                    "INSERT INTO users (id, username, email, password_hash, full_name, phone, is_active, is_admin) "
                    "VALUES (:id, :username, :email, :password_hash, :full_name, :phone, true, false) "
                    "ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email"
                ),
                {
                    "id": uid,
                    "username": f"obs_user_{uid}",
                    "email": f"obs_user_{uid}@test.com",
                    "password_hash": User.hash_password("pass"),
                    "full_name": "Obs User",
                    "phone": "13800138000",
                },
            )
        await session.commit()
        now = utc_now()
        # execution 1: recent, policy agent, high confidence, no transfer
        ex1 = GraphExecutionLog(
            thread_id=f"t1_{uuid.uuid4().hex[:8]}",
            user_id=1,
            intent_category="policy",
            final_agent="policy_agent",
            confidence_score=0.95,
            needs_human_transfer=False,
            total_latency_ms=120,
            created_at=now,
        )
        session.add(ex1)
        await session.commit()
        await session.refresh(ex1)
        assert ex1.id is not None

        session.add_all(
            [
                GraphNodeLog(
                    execution_id=ex1.id, node_name="router_node", latency_ms=10, created_at=now
                ),
                GraphNodeLog(
                    execution_id=ex1.id, node_name="policy_agent", latency_ms=100, created_at=now
                ),
            ]
        )

        # execution 2: recent, order agent, low confidence, transfer
        ex2 = GraphExecutionLog(
            thread_id=f"t2_{uuid.uuid4().hex[:8]}",
            user_id=2,
            intent_category="order",
            final_agent="order_agent",
            confidence_score=0.55,
            needs_human_transfer=True,
            total_latency_ms=250,
            created_at=now,
        )
        session.add(ex2)
        await session.commit()
        await session.refresh(ex2)
        assert ex2.id is not None

        session.add_all(
            [
                GraphNodeLog(
                    execution_id=ex2.id, node_name="router_node", latency_ms=20, created_at=now
                ),
                GraphNodeLog(
                    execution_id=ex2.id, node_name="order_agent", latency_ms=200, created_at=now
                ),
            ]
        )

        # execution 3: older than 7 days (to test range filtering)
        ex3 = GraphExecutionLog(
            thread_id=f"t3_{uuid.uuid4().hex[:8]}",
            user_id=3,
            intent_category="refund",
            final_agent="order_agent",
            confidence_score=0.75,
            needs_human_transfer=False,
            total_latency_ms=300,
            created_at=now - timedelta(days=10),
        )
        session.add(ex3)
        await session.commit()
        await session.refresh(ex3)
        assert ex3.id is not None

        session.add_all(
            [
                GraphNodeLog(
                    execution_id=ex3.id,
                    node_name="router_node",
                    latency_ms=30,
                    created_at=now - timedelta(days=10),
                ),
                GraphNodeLog(
                    execution_id=ex3.id,
                    node_name="order_agent",
                    latency_ms=250,
                    created_at=now - timedelta(days=10),
                ),
            ]
        )

        await session.commit()


@pytest.mark.asyncio
async def test_metrics_endpoints(client):
    await seed_logs()
    _, token = await create_admin_user()

    # sessions
    response = await client.get(
        "/api/v1/admin/metrics/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    sessions = response.json()
    assert "24h" in sessions
    assert "7d" in sessions
    assert "30d" in sessions
    assert sessions["24h"] == 2
    assert sessions["7d"] == 2
    assert sessions["30d"] == 3

    # transfers
    response = await client.get(
        "/api/v1/admin/metrics/transfers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    transfers = response.json()
    assert isinstance(transfers, list)
    by_agent = {item["final_agent"]: item for item in transfers}
    assert by_agent["policy_agent"]["total"] == 1
    assert by_agent["policy_agent"]["transfers"] == 0
    assert by_agent["policy_agent"]["transfer_rate"] == 0.0
    assert by_agent["order_agent"]["total"] == 2
    assert by_agent["order_agent"]["transfers"] == 1
    assert by_agent["order_agent"]["transfer_rate"] == 0.5

    # confidence
    response = await client.get(
        "/api/v1/admin/metrics/confidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    confidence = response.json()
    assert isinstance(confidence, list)
    by_agent = {item["final_agent"]: item for item in confidence}
    assert by_agent["policy_agent"]["avg_confidence"] == pytest.approx(0.95, 0.01)
    assert by_agent["order_agent"]["avg_confidence"] == pytest.approx(0.65, 0.01)

    # latency
    response = await client.get(
        "/api/v1/admin/metrics/latency",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    latency = response.json()
    assert isinstance(latency, list)
    by_node = {item["node_name"]: item for item in latency}
    assert by_node["router_node"]["p99_latency_ms"] == pytest.approx(29.8, 0.01)
    assert by_node["policy_agent"]["p99_latency_ms"] == pytest.approx(100.0, 0.01)
    assert by_node["order_agent"]["p99_latency_ms"] == pytest.approx(250.0, 0.01)


@pytest.mark.asyncio
async def test_metrics_rejects_non_admin(client):
    unique = uuid.uuid4().hex[:8]
    async with async_session_maker() as session:
        user = User(
            username=f"user_{unique}",
            password_hash=User.hash_password("userpass"),
            email=f"user_{unique}@user.com",
            full_name="Regular User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id, is_admin=False)

    response = await client.get(
        "/api/v1/admin/metrics/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
