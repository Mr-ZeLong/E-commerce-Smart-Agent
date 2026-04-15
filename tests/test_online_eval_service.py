from datetime import UTC, datetime, timedelta

import pytest

from app.models.evaluation import MessageFeedback
from app.models.user import User
from app.services.online_eval import OnlineEvalService


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
) -> MessageFeedback:
    fb = MessageFeedback(
        user_id=user_id,
        thread_id="thread-1",
        message_index=0,
        score=score,
        created_at=created_at or datetime.now(UTC),
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
