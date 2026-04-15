import pytest
from sqlmodel import select

from app.memory.extractor import FactExtractor
from app.models.memory import UserFact
from app.models.user import User
from app.tasks.memory_tasks import extract_and_save_facts


def test_extract_and_save_facts_deduplicates_existing_facts(db_sync_session, deterministic_llm):
    user = User(
        username="memory_user_1",
        password_hash=User.hash_password("testpass"),
        email="memory1@test.com",
        full_name="Test User",
    )
    db_sync_session.add(user)
    db_sync_session.commit()
    db_sync_session.refresh(user)
    assert user.id is not None

    thread_id = "t1"

    existing = UserFact(
        user_id=user.id,
        fact_type="preference",
        content="likes fast shipping",
        confidence=0.9,
        source_thread_id=thread_id,
    )
    db_sync_session.add(existing)
    db_sync_session.commit()

    deterministic_llm.responses = [
        (
            "",
            '[{"fact_type":"preference","content":"likes fast shipping","confidence":0.9},'
            '{"fact_type":"general","content":"is a vip","confidence":0.8}]',
        )
    ]

    result = extract_and_save_facts.run(
        user_id=user.id,
        thread_id=thread_id,
        history_json='[{"role":"user","content":"hi"}]',
        question="send it fast",
        answer="sure, expedited shipping available",
        session=db_sync_session,
        extractor=FactExtractor(llm=deterministic_llm),
    )

    assert result["status"] == "success"
    assert result["facts_extracted"] == 1

    facts = db_sync_session.exec(
        select(UserFact).where(
            UserFact.user_id == user.id,
            UserFact.source_thread_id == thread_id,
        )
    ).all()
    assert len(facts) == 2
    contents = {f.content for f in facts}
    assert contents == {"likes fast shipping", "is a vip"}


def test_extract_and_save_facts_saves_all_when_no_existing_facts(
    db_sync_session, deterministic_llm
):
    user = User(
        username="memory_user_2",
        password_hash=User.hash_password("testpass"),
        email="memory2@test.com",
        full_name="Test User",
    )
    db_sync_session.add(user)
    db_sync_session.commit()
    db_sync_session.refresh(user)
    assert user.id is not None

    thread_id = "t2"

    deterministic_llm.responses = [
        (
            "",
            '[{"fact_type":"preference","content":"likes red","confidence":0.9}]',
        )
    ]

    result = extract_and_save_facts.run(
        user_id=user.id,
        thread_id=thread_id,
        history_json="[]",
        question="what color",
        answer="red",
        session=db_sync_session,
        extractor=FactExtractor(llm=deterministic_llm),
    )

    assert result["status"] == "success"
    assert result["facts_extracted"] == 1

    facts = db_sync_session.exec(
        select(UserFact).where(
            UserFact.user_id == user.id,
            UserFact.source_thread_id == thread_id,
        )
    ).all()
    assert len(facts) == 1
    assert facts[0].content == "likes red"
