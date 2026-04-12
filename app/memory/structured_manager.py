from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.memory import InteractionSummary, UserFact, UserPreference, UserProfile


class StructuredMemoryManager:
    """Structured memory manager for user profiles, facts, preferences and interaction summaries."""

    async def get_user_facts(
        self,
        session: AsyncSession,
        user_id: int,
        fact_types: list[str] | None = None,
        limit: int = 3,
    ) -> list[UserFact]:
        stmt = (
            select(UserFact)
            .where(UserFact.user_id == user_id)
            .order_by(desc(UserFact.confidence), desc(UserFact.created_at))
            .limit(limit)
        )
        if fact_types:
            stmt = stmt.where(UserFact.fact_type.in_(fact_types))  # type: ignore
        result = await session.exec(stmt)
        return list(result.all())

    async def get_user_profile(self, session: AsyncSession, user_id: int) -> UserProfile | None:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.exec(stmt)
        return result.one_or_none()

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
        return record

    async def get_user_preferences(
        self, session: AsyncSession, user_id: int
    ) -> list[UserPreference]:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await session.exec(stmt)
        return list(result.all())

    async def get_recent_summaries(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 2,
    ) -> list[InteractionSummary]:
        stmt = (
            select(InteractionSummary)
            .where(InteractionSummary.user_id == user_id)
            .order_by(desc(InteractionSummary.created_at))
            .limit(limit)
        )
        result = await session.exec(stmt)
        return list(result.all())
