"""Tests for continuous improvement service."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.models.observability import GraphExecutionLog
from app.models.user import User
from app.services.continuous_improvement import (
    AuditBatch,
    AuditSample,
    ContinuousImprovementService,
    RootCause,
)


async def create_test_user(db_session) -> User:
    user = User(
        username="test_user",
        password_hash=User.hash_password("testpass"),
        email="test@test.com",
        full_name="Test User",
        phone="13800138000",
        is_admin=False,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_sample_conversations_basic(db_session):
    user = await create_test_user(db_session)
    assert user.id is not None
    user_id = user.id
    now = datetime.now(UTC)
    logs = [
        GraphExecutionLog(
            thread_id="t1",
            user_id=user_id,
            intent_category="ORDER",
            final_agent="order_agent",
            confidence_score=0.8,
            needs_human_transfer=False,
            created_at=now - timedelta(hours=1),
        ),
        GraphExecutionLog(
            thread_id="t2",
            user_id=user_id,
            intent_category="POLICY",
            final_agent="policy_agent",
            confidence_score=0.9,
            needs_human_transfer=False,
            created_at=now - timedelta(hours=2),
        ),
        GraphExecutionLog(
            thread_id="t3",
            user_id=user_id,
            intent_category="ORDER",
            final_agent="order_agent",
            confidence_score=0.6,
            needs_human_transfer=True,
            created_at=now - timedelta(hours=3),
        ),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()

    service = ContinuousImprovementService(db_session)
    batch = await service.sample_conversations(days=1, sample_rate=0.5)

    assert batch.total_conversations >= 3
    assert batch.sample_size >= 1
    assert len(batch.samples) == batch.sample_size

    for log in logs:
        await db_session.delete(log)
    await db_session.commit()


@pytest.mark.asyncio
async def test_sample_conversations_stratified(db_session):
    user = await create_test_user(db_session)
    assert user.id is not None
    user_id = user.id
    now = datetime.now(UTC)
    logs = []
    for i in range(10):
        logs.append(
            GraphExecutionLog(
                thread_id=f"order_{i}",
                user_id=user_id,
                intent_category="ORDER",
                final_agent="order_agent",
                confidence_score=0.8,
                needs_human_transfer=False,
                created_at=now - timedelta(hours=i),
            )
        )
    for i in range(10):
        logs.append(
            GraphExecutionLog(
                thread_id=f"policy_{i}",
                user_id=user_id,
                intent_category="POLICY",
                final_agent="policy_agent",
                confidence_score=0.9,
                needs_human_transfer=False,
                created_at=now - timedelta(hours=i + 10),
            )
        )

    for log in logs:
        db_session.add(log)
    await db_session.commit()

    service = ContinuousImprovementService(db_session)
    batch = await service.sample_conversations(days=1, sample_rate=0.2, stratify_by_intent=True)

    assert batch.total_conversations >= 20
    assert batch.sample_size >= 4

    order_samples = [s for s in batch.samples if s.intent_category == "ORDER"]
    policy_samples = [s for s in batch.samples if s.intent_category == "POLICY"]
    assert len(order_samples) >= 1
    assert len(policy_samples) >= 1

    for log in logs:
        await db_session.delete(log)
    await db_session.commit()


@pytest.mark.asyncio
async def test_run_audit(db_session):
    user = await create_test_user(db_session)
    assert user.id is not None
    user_id = user.id
    now = datetime.now(UTC)
    log = GraphExecutionLog(
        thread_id="t1",
        user_id=user_id,
        intent_category="ORDER",
        final_agent="order_agent",
        confidence_score=0.8,
        needs_human_transfer=False,
        created_at=now - timedelta(hours=1),
    )
    db_session.add(log)
    await db_session.commit()

    service = ContinuousImprovementService(db_session)
    batch = await service.run_audit(days=1, sample_rate=1.0)

    assert batch.total_conversations >= 1
    assert batch.sample_size >= 1
    assert any(s.thread_id == "t1" for s in batch.samples)

    await db_session.delete(log)
    await db_session.commit()


def test_merge_feedback_into_dataset(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    records = [
        {
            "query": "existing query",
            "expected_intent": "ORDER",
            "expected_slots": {},
            "expected_answer_fragment": "",
            "expected_audit_level": "auto",
            "dimension": "order_query",
        }
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8"
    )

    batch = AuditBatch(
        week_start="2024-01-01",
        total_conversations=100,
        sample_size=5,
        samples=[
            AuditSample(
                thread_id="new_thread",
                user_id=1,
                intent_category="ORDER",
                final_agent="order_agent",
                confidence_score=0.5,
                needs_human_transfer=True,
                created_at=datetime.now(UTC),
                root_cause=RootCause.INTENT_ERROR,
            )
        ],
    )

    result = ContinuousImprovementService.merge_feedback_into_dataset(dataset_path, batch)

    assert result.total_records == 2
    assert any("[AUDIT]" in r.query for r in result.records)


def test_merge_feedback_no_duplicates(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    records = [
        {
            "query": "[AUDIT] existing_thread",
            "expected_intent": "ORDER",
            "expected_slots": {},
            "expected_answer_fragment": "",
            "expected_audit_level": "auto",
            "dimension": "order_query",
        }
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8"
    )

    batch = AuditBatch(
        week_start="2024-01-01",
        total_conversations=100,
        sample_size=1,
        samples=[
            AuditSample(
                thread_id="existing_thread",
                user_id=1,
                intent_category="ORDER",
                final_agent="order_agent",
                confidence_score=0.5,
                needs_human_transfer=True,
                created_at=datetime.now(UTC),
                root_cause=RootCause.INTENT_ERROR,
            )
        ],
    )

    result = ContinuousImprovementService.merge_feedback_into_dataset(dataset_path, batch)

    assert result.total_records == 1


def test_root_cause_enum():
    assert RootCause.INTENT_ERROR.value == "intent_error"
    assert RootCause.HALLUCINATION.value == "hallucination"
    assert RootCause.LATENCY.value == "latency"
    assert RootCause.SAFETY.value == "safety"
    assert RootCause.TONE.value == "tone"
    assert RootCause.OTHER.value == "other"
