import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.llm_factory import create_openai_llm
from app.models.evaluation import MessageFeedback, QualityScore, ScoreTypeEnum, SentimentEnum

logger = logging.getLogger(__name__)

FEEDBACK_SCORE_MAP = {
    SentimentEnum.UP.value: 1,
    SentimentEnum.NEUTRAL.value: 0,
    SentimentEnum.DOWN.value: -1,
}


class OnlineEvalService:
    async def submit_feedback(
        self,
        db: AsyncSession,
        user_id: int,
        thread_id: str,
        message_index: int,
        sentiment: str,
        comment: str | None = None,
    ) -> MessageFeedback:
        score = FEEDBACK_SCORE_MAP.get(sentiment, 0)
        feedback = MessageFeedback(
            user_id=user_id,
            thread_id=thread_id,
            message_index=message_index,
            score=score,
            comment=comment,
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        return feedback

    async def list_feedback(
        self,
        db: AsyncSession,
        sentiment: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[MessageFeedback], int]:
        stmt = select(MessageFeedback).order_by(desc(MessageFeedback.created_at))
        count_stmt = select(func.count()).select_from(MessageFeedback)

        if sentiment:
            target_score = FEEDBACK_SCORE_MAP.get(sentiment)
            if target_score is not None:
                stmt = stmt.where(MessageFeedback.score == target_score)
                count_stmt = count_stmt.where(MessageFeedback.score == target_score)
        if date_from:
            stmt = stmt.where(MessageFeedback.created_at >= date_from)
            count_stmt = count_stmt.where(MessageFeedback.created_at >= date_from)
        if date_to:
            stmt = stmt.where(MessageFeedback.created_at <= date_to)
            count_stmt = count_stmt.where(MessageFeedback.created_at <= date_to)

        result = await db.exec(stmt.offset(offset).limit(limit))
        count_result = await db.exec(count_stmt)
        return list(result.all()), count_result.one()

    async def get_csat_trend(self, db: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)
        stmt = (
            select(
                func.date(MessageFeedback.created_at).label("day"),
                func.sum(func.case((MessageFeedback.score == 1, 1), else_=0)).label("up"),
                func.sum(func.case((MessageFeedback.score == -1, 1), else_=0)).label("down"),
            )
            .where(MessageFeedback.created_at >= since)
            .group_by(func.date(MessageFeedback.created_at))
            .order_by(func.date(MessageFeedback.created_at))
        )
        result = await db.exec(stmt)
        rows = result.all()
        trend = []
        for row in rows:
            up = int(row[1] or 0)
            down = int(row[2] or 0)
            total = up + down
            csat = round(up / total, 4) if total > 0 else 1.0
            trend.append(
                {
                    "date": str(row[0]),
                    "thumbs_up": up,
                    "thumbs_down": down,
                    "csat": csat,
                }
            )
        return trend

    async def compute_quality_scores(
        self,
        db: AsyncSession,
        sample_size: int = 50,
    ) -> list[QualityScore]:
        from sqlalchemy import text

        stmt = (
            select(MessageFeedback)
            .where(text("comment IS NOT NULL"))
            .order_by(desc(MessageFeedback.created_at))
            .limit(sample_size)
        )
        result = await db.exec(stmt)
        feedbacks = list(result.all())
        if not feedbacks:
            return []

        llm = create_openai_llm()
        scores: list[QualityScore] = []
        today = date.today()
        for fb in feedbacks:
            prompt = (
                "请对以下客服回复质量进行 1-5 分评分，并给出三个维度评分："
                "helpfulness, accuracy, empathy。只返回 JSON："
                '{"helpfulness": int, "accuracy": int, "empathy": int}\n\n评论：'
                + (fb.comment or "")
            )
            try:
                response = await llm.ainvoke([{"role": "user", "content": prompt}])
                content = str(response.content)
                import json

                data = json.loads(content.strip("`\n ").replace("```json", "").replace("```", ""))
                for score_type in ScoreTypeEnum:
                    value = data.get(score_type.value)
                    if value is not None:
                        qs = QualityScore(
                            score_date=today,
                            score_type=score_type.value,
                            explicit_upvotes=1 if fb.score == 1 else 0,
                            explicit_downvotes=1 if fb.score == -1 else 0,
                        )
                        db.add(qs)
                        scores.append(qs)
            except Exception:
                logger.exception("Quality score LLM evaluation failed")
        await db.commit()
        return scores
