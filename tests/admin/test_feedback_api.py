import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.evaluation import MessageFeedback, QualityScore
from tests.test_admin_api import create_admin_user, create_regular_user


async def create_feedback(
    user_id: int, thread_id: str, message_index: int, score: int = 1, comment: str | None = None
) -> MessageFeedback:
    async with async_session_maker() as session:
        feedback = MessageFeedback(
            user_id=user_id,
            thread_id=thread_id,
            message_index=message_index,
            score=score,
            comment=comment,
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        return feedback


@pytest.mark.asyncio
async def test_list_feedback(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    feedback = await create_feedback(user.id or 0, thread_id, 0, score=1, comment="Great!")

    response = await client.get(
        "/api/v1/admin/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    item_ids = [item["id"] for item in data["items"]]
    assert feedback.id in item_ids


@pytest.mark.asyncio
async def test_list_feedback_with_sentiment_filter(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    await create_feedback(user.id or 0, thread_id, 0, score=-1, comment="Bad")

    response = await client.get(
        "/api/v1/admin/feedback?sentiment=down",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(item["score"] == -1 for item in data["items"])


@pytest.mark.asyncio
async def test_list_feedback_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_feedback(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    await create_feedback(user.id or 0, thread_id, 0, score=1, comment="Good")

    response = await client.get(
        "/api/v1/admin/feedback/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "filename" in data
    assert data["content"].startswith("id,user_id,thread_id")
    assert "Good" in data["content"]


@pytest.mark.asyncio
async def test_export_feedback_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/feedback/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_csat_trend(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    await create_feedback(user.id or 0, thread_id, 0, score=1)

    response = await client.get(
        "/api/v1/admin/feedback/csat?days=30",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "days" in data
    assert "trend" in data
    assert isinstance(data["trend"], list)
    assert len(data["trend"]) >= 1


@pytest.mark.asyncio
async def test_get_csat_trend_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/feedback/csat",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_run_quality_score_no_comments(client):
    _admin, token = await create_admin_user()

    response = await client.post(
        "/api/v1/admin/feedback/quality-score/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"sample_size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["scored_count"] >= 0


@pytest.mark.asyncio
async def test_run_quality_score_with_comments(client):
    _admin, token = await create_admin_user()
    user = await create_regular_user()
    thread_id = f"thread_{uuid.uuid4().hex[:8]}"
    await create_feedback(user.id or 0, thread_id, 0, score=1, comment="Very helpful")

    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = '{"helpfulness": 5, "accuracy": 4, "empathy": 5}'
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.online_eval.create_openai_llm", return_value=mock_llm):
        response = await client.post(
            "/api/v1/admin/feedback/quality-score/run",
            headers={"Authorization": f"Bearer {token}"},
            json={"sample_size": 10},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["scored_count"] >= 1

    async with async_session_maker() as session:
        result = await session.exec(select(QualityScore))
        scores = result.all()
        assert len(scores) >= 1


@pytest.mark.asyncio
async def test_run_quality_score_rejects_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.post(
        "/api/v1/admin/feedback/quality-score/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"sample_size": 10},
    )
    assert response.status_code == 403
