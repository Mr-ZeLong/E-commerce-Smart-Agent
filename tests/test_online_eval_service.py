from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.evaluation import MessageFeedback
from app.models.user import User
from app.services.online_eval import FEEDBACK_SCORE_MAP, OnlineEvalService


@pytest.fixture
def online_eval_service() -> OnlineEvalService:
    return OnlineEvalService()


async def _create_test_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name="Test User",
        password_hash=User.hash_password("testpass"),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_feedback(
    session,
    user_id: int,
    score: int,
    created_at: datetime | None = None,
    comment: str | None = None,
) -> MessageFeedback:
    fb = MessageFeedback(
        user_id=user_id,
        thread_id="thread-1",
        message_index=0,
        score=score,
        created_at=created_at or datetime.now(UTC),
        comment=comment,
    )
    session.add(fb)
    await session.flush()
    await session.refresh(fb)
    return fb


@pytest.mark.asyncio
async def test_get_csat_trend_aggregates_by_day(online_eval_service: OnlineEvalService, db_session):
    """Regression test for func.case SQLAlchemy 2.0 compatibility bug.

    The original code used `func.case((...), else_=0)` which is invalid in
    SQLAlchemy 2.0 and caused a 500 on /api/v1/admin/analytics/csat.
    """
    user = await _create_test_user(db_session, "csat_user")
    assert user.id is not None

    today = datetime.now(UTC)
    yesterday = today - timedelta(days=1)

    # Today: 2 up, 1 down
    await _create_feedback(db_session, user.id, score=1, created_at=today)
    await _create_feedback(db_session, user.id, score=1, created_at=today)
    await _create_feedback(db_session, user.id, score=-1, created_at=today)

    # Yesterday: 1 up, 0 down
    await _create_feedback(db_session, user.id, score=1, created_at=yesterday)

    trend = await online_eval_service.get_csat_trend(db_session, days=7)

    assert len(trend) == 2

    # Verify today's stats
    today_row = next(r for r in trend if r["date"] == str(today.date()))
    assert today_row["thumbs_up"] == 2
    assert today_row["thumbs_down"] == 1
    assert today_row["csat"] == round(2 / 3, 4)

    # Verify yesterday's stats
    yesterday_row = next(r for r in trend if r["date"] == str(yesterday.date()))
    assert yesterday_row["thumbs_up"] == 1
    assert yesterday_row["thumbs_down"] == 0
    assert yesterday_row["csat"] == 1.0


@pytest.mark.asyncio
async def test_get_csat_trend_empty_returns_one(online_eval_service: OnlineEvalService, db_session):
    """When no feedback exists, CSAT defaults to 1.0 (perfect satisfaction)."""
    trend = await online_eval_service.get_csat_trend(db_session, days=7)
    assert trend == []


@pytest.mark.asyncio
async def test_submit_feedback(online_eval_service: OnlineEvalService, db_session):
    user = await _create_test_user(db_session, "feedback_user")
    assert user.id is not None

    fb = await online_eval_service.submit_feedback(
        db_session,
        user_id=user.id,
        thread_id="thread-fb",
        message_index=2,
        sentiment="up",
        comment="Great!",
    )
    assert fb.user_id == user.id
    assert fb.thread_id == "thread-fb"
    assert fb.score == FEEDBACK_SCORE_MAP["up"]
    assert fb.comment == "Great!"


@pytest.mark.asyncio
async def test_list_feedback_filters_by_sentiment(
    online_eval_service: OnlineEvalService, db_session
):
    user = await _create_test_user(db_session, "list_fb_user")
    assert user.id is not None

    await _create_feedback(db_session, user.id, score=1)
    await _create_feedback(db_session, user.id, score=-1)

    ups, up_count = await online_eval_service.list_feedback(db_session, sentiment="up")
    assert up_count == 1
    assert all(f.score == 1 for f in ups)

    downs, down_count = await online_eval_service.list_feedback(db_session, sentiment="down")
    assert down_count == 1
    assert all(f.score == -1 for f in downs)


@pytest.mark.asyncio
async def test_list_feedback_pagination(online_eval_service: OnlineEvalService, db_session):
    user = await _create_test_user(db_session, "pag_fb_user")
    assert user.id is not None

    for _ in range(5):
        await _create_feedback(db_session, user.id, score=1)

    page, total = await online_eval_service.list_feedback(db_session, offset=0, limit=2)
    assert total == 5
    assert len(page) == 2


@pytest.mark.asyncio
async def test_compute_quality_scores_with_no_comment(
    online_eval_service: OnlineEvalService, db_session
):
    result = await online_eval_service.compute_quality_scores(db_session, sample_size=10)
    assert result == []


@pytest.mark.asyncio
async def test_compute_quality_scores_with_llm(online_eval_service: OnlineEvalService, db_session):
    user = await _create_test_user(db_session, "qs_user")
    assert user.id is not None

    await _create_feedback(db_session, user.id, score=1, comment="Very helpful")

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = '{"helpfulness": 4, "accuracy": 5, "empathy": 3}'

    with patch("app.services.online_eval.create_openai_llm", return_value=mock_llm):
        scores = await online_eval_service.compute_quality_scores(db_session, sample_size=10)

    assert len(scores) == 3
    score_types = {s.score_type for s in scores}
    assert score_types == {"helpfulness", "accuracy", "empathy"}
    mock_llm.ainvoke.assert_awaited_once()
