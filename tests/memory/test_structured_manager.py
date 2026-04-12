import pytest

from app.core.database import async_session_maker
from app.memory.structured_manager import StructuredMemoryManager
from app.models.memory import UserFact, UserPreference, UserProfile


@pytest.fixture
def manager():
    return StructuredMemoryManager()


@pytest.mark.asyncio
async def test_get_user_profile_found(manager):
    async with async_session_maker() as session:
        profile = UserProfile(
            user_id=42,
            membership_level="gold",
            preferred_language="zh",
            timezone="Asia/Shanghai",
            total_orders=10,
            lifetime_value=5000.0,
        )
        session.add(profile)
        await session.commit()

        result = await manager.get_user_profile(session, 42)
        assert result is not None
        assert result.membership_level == "gold"
        assert result.total_orders == 10


@pytest.mark.asyncio
async def test_get_user_profile_not_found(manager):
    async with async_session_maker() as session:
        result = await manager.get_user_profile(session, 999999)
        assert result is None


@pytest.mark.asyncio
async def test_get_user_facts_with_filter(manager):
    async with async_session_maker() as session:
        fact1 = UserFact(user_id=1, fact_type="preference", content="likes blue", confidence=0.9)
        fact2 = UserFact(user_id=1, fact_type="order", content="ordered shoes", confidence=0.8)
        fact3 = UserFact(user_id=1, fact_type="preference", content="likes red", confidence=0.95)
        session.add_all([fact1, fact2, fact3])
        await session.commit()

        results = await manager.get_user_facts(session, 1, fact_types=["preference"], limit=2)
        assert len(results) == 2
        assert results[0].content == "likes red"
        assert results[1].content == "likes blue"


@pytest.mark.asyncio
async def test_get_user_facts_without_filter(manager):
    async with async_session_maker() as session:
        fact = UserFact(user_id=2, fact_type="general", content="fact", confidence=0.5)
        session.add(fact)
        await session.commit()

        results = await manager.get_user_facts(session, 2)
        assert len(results) == 1
        assert results[0].fact_type == "general"


@pytest.mark.asyncio
async def test_save_interaction_summary(manager):
    async with async_session_maker() as session:
        record = await manager.save_interaction_summary(
            session=session,
            user_id=5,
            thread_id="thread-abc",
            summary="User asked about shipping.",
            resolved_intent="LOGISTICS",
            satisfaction_score=4.5,
        )
        await session.commit()

        assert record.id is not None
        assert record.summary_text == "User asked about shipping."
        assert record.resolved_intent == "LOGISTICS"
        assert record.satisfaction_score == 4.5


@pytest.mark.asyncio
async def test_save_user_fact(manager):
    async with async_session_maker() as session:
        record = await manager.save_user_fact(
            session=session,
            user_id=7,
            fact_type="preference",
            content="prefers fast shipping",
            confidence=0.85,
            source_thread_id="thread-xyz",
        )
        await session.commit()

        assert record.id is not None
        assert record.content == "prefers fast shipping"
        assert record.confidence == 0.85
        assert record.source_thread_id == "thread-xyz"


@pytest.mark.asyncio
async def test_get_user_preferences(manager):
    async with async_session_maker() as session:
        pref1 = UserPreference(user_id=3, preference_key="theme", preference_value="dark")
        pref2 = UserPreference(user_id=3, preference_key="notifications", preference_value="on")
        session.add_all([pref1, pref2])
        await session.commit()

        results = await manager.get_user_preferences(session, 3)
        assert len(results) == 2
        keys = {p.preference_key for p in results}
        assert keys == {"theme", "notifications"}


@pytest.mark.asyncio
async def test_get_user_preferences_empty(manager):
    async with async_session_maker() as session:
        results = await manager.get_user_preferences(session, 999999)
        assert results == []
