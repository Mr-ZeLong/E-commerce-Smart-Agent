from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.cache import CacheManager
from app.models.memory import InteractionSummary, UserFact, UserPreference, UserProfile


class StructuredMemoryManager:
    """Structured memory manager for user profiles, facts, preferences and interaction summaries."""

    def __init__(self, cache_manager: CacheManager | None = None) -> None:
        self._cache = cache_manager

    async def get_user_facts(
        self,
        session: AsyncSession,
        user_id: int,
        fact_types: list[str] | None = None,
        limit: int = 3,
    ) -> list[UserFact]:
        if self._cache is not None:
            cached = await self._cache.get_facts(user_id, fact_types=fact_types, limit=limit)
            if cached is not None:
                return [UserFact.model_validate(f) for f in cached]

        stmt = (
            select(UserFact)
            .where(UserFact.user_id == user_id)
            .order_by(desc(UserFact.confidence), desc(UserFact.created_at))
            .limit(limit)
        )
        if fact_types:
            stmt = stmt.where(UserFact.fact_type.in_(fact_types))  # type: ignore
        result = await session.exec(stmt)
        facts = list(result.all())

        if self._cache is not None:
            await self._cache.set_facts(
                user_id, [f.model_dump() for f in facts], fact_types=fact_types, limit=limit
            )

        return facts

    async def get_user_profile(self, session: AsyncSession, user_id: int) -> UserProfile | None:
        if self._cache is not None:
            cached = await self._cache.get_profile(user_id)
            if cached is not None:
                return UserProfile.model_validate(cached)

        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.exec(stmt)
        profile = result.one_or_none()

        if profile is not None and self._cache is not None:
            await self._cache.set_profile(user_id, profile.model_dump())

        return profile

    async def save_interaction_summary(
        self,
        session: AsyncSession,
        user_id: int,
        thread_id: str,
        summary: str,
        resolved_intent: str | None = None,
        satisfaction_score: float | None = None,
    ) -> InteractionSummary:
        record = InteractionSummary(
            user_id=user_id,
            thread_id=thread_id,
            summary_text=summary,
            resolved_intent=resolved_intent or "",
            satisfaction_score=satisfaction_score,
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        if self._cache is not None:
            await self._cache.invalidate_summaries(user_id)
        return record

    async def save_user_fact(
        self,
        session: AsyncSession,
        user_id: int,
        fact_type: str,
        content: str,
        confidence: float,
        source_thread_id: str | None = None,
    ) -> UserFact:
        record = UserFact(
            user_id=user_id,
            fact_type=fact_type,
            content=content,
            confidence=confidence,
            source_thread_id=source_thread_id,
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        if self._cache is not None:
            await self._cache.invalidate_facts(user_id)
        return record

    async def get_user_preferences(
        self, session: AsyncSession, user_id: int
    ) -> list[UserPreference]:
        if self._cache is not None:
            cached = await self._cache.get_preferences(user_id)
            if cached is not None:
                return [UserPreference.model_validate(p) for p in cached]

        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await session.exec(stmt)
        preferences = list(result.all())

        if self._cache is not None:
            await self._cache.set_preferences(user_id, [p.model_dump() for p in preferences])

        return preferences

    async def get_recent_summaries(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 2,
    ) -> list[InteractionSummary]:
        if self._cache is not None:
            cached = await self._cache.get_summaries(user_id, limit=limit)
            if cached is not None:
                return [InteractionSummary.model_validate(s) for s in cached]

        stmt = (
            select(InteractionSummary)
            .where(InteractionSummary.user_id == user_id)
            .order_by(desc(InteractionSummary.created_at))
            .limit(limit)
        )
        result = await session.exec(stmt)
        summaries = list(result.all())

        if self._cache is not None:
            await self._cache.set_summaries(
                user_id, [s.model_dump() for s in summaries], limit=limit
            )

        return summaries
