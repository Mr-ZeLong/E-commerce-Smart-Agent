from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.utils import utc_now
from app.models.token_usage import (
    OptimizationSuggestion,
    TokenUsageLog,
)

logger = logging.getLogger(__name__)


class TokenTracker:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_usage(
        self,
        user_id: int,
        thread_id: str,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        query_text: str | None = None,
        model_name: str | None = None,
    ) -> TokenUsageLog:
        total = input_tokens + output_tokens
        log = TokenUsageLog(
            user_id=user_id,
            thread_id=thread_id,
            agent_type=agent_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            query_text=query_text,
            model_name=model_name,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)

        if total >= 10000:
            logger.warning("High token usage detected: %d tokens for user %d", total, user_id)

        await self._maybe_generate_suggestions(log)
        return log

    async def _maybe_generate_suggestions(self, log: TokenUsageLog) -> None:
        if log.total_tokens >= 8000:
            existing = await self.session.exec(
                select(OptimizationSuggestion)
                .where(OptimizationSuggestion.thread_id == log.thread_id)
                .where(OptimizationSuggestion.suggestion_type == "high_context_window")
            )
            if existing.one_or_none() is None:
                suggestion = OptimizationSuggestion(
                    user_id=log.user_id,
                    thread_id=log.thread_id,
                    suggestion_type="high_context_window",
                    message="High token usage detected - review context window. Consider summarizing conversation history or reducing retrieval top-k.",
                    context_data={"total_tokens": log.total_tokens, "agent_type": log.agent_type},
                )
                self.session.add(suggestion)
                await self.session.commit()

        recent = await self.session.exec(
            select(func.count(TokenUsageLog.id))  # type: ignore
            .where(TokenUsageLog.user_id == log.user_id)
            .where(TokenUsageLog.created_at >= utc_now() - timedelta(hours=1))  # type: ignore
        )
        recent_count = recent.one() or 0
        if recent_count >= 10:
            existing = await self.session.exec(
                select(OptimizationSuggestion)
                .where(OptimizationSuggestion.user_id == log.user_id)
                .where(OptimizationSuggestion.suggestion_type == "frequent_queries")
                .where(OptimizationSuggestion.created_at >= utc_now() - timedelta(days=1))  # type: ignore
            )
            if existing.one_or_none() is None:
                suggestion = OptimizationSuggestion(
                    user_id=log.user_id,
                    suggestion_type="frequent_queries",
                    message="Consider caching for frequent queries. This user has made many requests recently.",
                    context_data={"recent_count": recent_count},
                )
                self.session.add(suggestion)
                await self.session.commit()

    async def get_user_daily_aggregate(
        self, user_id: int, date: datetime | None = None
    ) -> dict[str, Any]:
        target = date or utc_now()
        start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        result = await self.session.exec(
            select(
                func.sum(TokenUsageLog.input_tokens).label("total_input"),  # type: ignore
                func.sum(TokenUsageLog.output_tokens).label("total_output"),  # type: ignore
                func.sum(TokenUsageLog.total_tokens).label("total"),  # type: ignore
                func.count(TokenUsageLog.id).label("query_count"),  # type: ignore
            )
            .where(TokenUsageLog.user_id == user_id)
            .where(TokenUsageLog.created_at >= start)  # type: ignore
            .where(TokenUsageLog.created_at < end)  # type: ignore
        )
        row = result.one()
        return {
            "user_id": user_id,
            "date": start.isoformat(),
            "input_tokens": row.total_input or 0,
            "output_tokens": row.total_output or 0,
            "total_tokens": row.total or 0,
            "query_count": row.query_count or 0,
        }

    async def get_user_period_aggregate(self, user_id: int, days: int = 7) -> dict[str, Any]:
        since = utc_now() - timedelta(days=days)
        result = await self.session.exec(
            select(
                func.sum(TokenUsageLog.input_tokens).label("total_input"),  # type: ignore
                func.sum(TokenUsageLog.output_tokens).label("total_output"),  # type: ignore
                func.sum(TokenUsageLog.total_tokens).label("total"),  # type: ignore
                func.count(TokenUsageLog.id).label("query_count"),  # type: ignore
            )
            .where(TokenUsageLog.user_id == user_id)
            .where(TokenUsageLog.created_at >= since)  # type: ignore
        )
        row = result.one()
        return {
            "user_id": user_id,
            "period_days": days,
            "input_tokens": row.total_input or 0,
            "output_tokens": row.total_output or 0,
            "total_tokens": row.total or 0,
            "query_count": row.query_count or 0,
        }

    async def get_agent_aggregate(self, days: int = 7) -> list[dict[str, Any]]:
        since = utc_now() - timedelta(days=days)
        result = await self.session.exec(
            select(
                TokenUsageLog.agent_type,
                func.sum(TokenUsageLog.input_tokens).label("total_input"),  # type: ignore
                func.sum(TokenUsageLog.output_tokens).label("total_output"),  # type: ignore
                func.sum(TokenUsageLog.total_tokens).label("total"),  # type: ignore
                func.count(TokenUsageLog.id).label("query_count"),  # type: ignore
            )
            .where(TokenUsageLog.created_at >= since)  # type: ignore
            .group_by(TokenUsageLog.agent_type)
            .order_by(func.sum(TokenUsageLog.total_tokens).desc())  # type: ignore
        )
        return [
            {
                "agent_type": row.agent_type,
                "input_tokens": row.total_input or 0,
                "output_tokens": row.total_output or 0,
                "total_tokens": row.total or 0,
                "query_count": row.query_count or 0,
            }
            for row in result.all()
        ]

    async def get_high_cost_queries(
        self, threshold: int = 10000, limit: int = 50
    ) -> list[dict[str, Any]]:
        result = await self.session.exec(
            select(TokenUsageLog)
            .where(TokenUsageLog.total_tokens >= threshold)  # type: ignore
            .order_by(TokenUsageLog.created_at.desc())  # type: ignore
            .limit(limit)
        )
        logs = result.all()
        return [
            {
                "id": log.id,
                "user_id": log.user_id,
                "thread_id": log.thread_id,
                "agent_type": log.agent_type,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "query_text": log.query_text,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in logs
        ]

    async def get_overall_usage(self, days: int = 7) -> dict[str, Any]:
        since = utc_now() - timedelta(days=days)
        result = await self.session.exec(
            select(
                func.sum(TokenUsageLog.input_tokens).label("total_input"),  # type: ignore
                func.sum(TokenUsageLog.output_tokens).label("total_output"),  # type: ignore
                func.sum(TokenUsageLog.total_tokens).label("total"),  # type: ignore
                func.count(TokenUsageLog.id).label("query_count"),  # type: ignore
                func.count(func.distinct(TokenUsageLog.user_id)).label("unique_users"),  # type: ignore
            ).where(TokenUsageLog.created_at >= since)  # type: ignore
        )
        row = result.one()
        return {
            "period_days": days,
            "input_tokens": row.total_input or 0,
            "output_tokens": row.total_output or 0,
            "total_tokens": row.total or 0,
            "query_count": row.query_count or 0,
            "unique_users": row.unique_users or 0,
        }

    async def check_anomalies(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        stmt = text(
            """
            SELECT user_id, SUM(total_tokens) as daily_total
            FROM token_usage_logs
            WHERE created_at >= :since
            GROUP BY user_id
            HAVING SUM(total_tokens) > 100000
            """
        ).bindparams(since=today_start)
        result = await self.session.exec(stmt)  # type: ignore
        for row in result.mappings().all():
            alerts.append(
                {
                    "type": "user_daily_exceeded",
                    "user_id": row["user_id"],
                    "daily_total": row["daily_total"],
                    "threshold": 100000,
                    "message": f"User {row['user_id']} exceeded 100K tokens today ({row['daily_total']} total)",
                }
            )

        high_cost = await self.get_high_cost_queries(threshold=10000, limit=10)
        for item in high_cost:
            alerts.append(
                {
                    "type": "single_query_high",
                    "user_id": item["user_id"],
                    "thread_id": item["thread_id"],
                    "total_tokens": item["total_tokens"],
                    "threshold": 10000,
                    "message": f"Query exceeded 10K tokens: {item['total_tokens']} tokens",
                }
            )

        return alerts

    async def get_suggestions(
        self, user_id: int | None = None, status: str | None = None, limit: int = 50
    ) -> list[OptimizationSuggestion]:
        stmt = select(OptimizationSuggestion).order_by(OptimizationSuggestion.created_at.desc())  # type: ignore
        if user_id is not None:
            stmt = stmt.where(OptimizationSuggestion.user_id == user_id)
        if status is not None:
            stmt = stmt.where(OptimizationSuggestion.status == status)
        stmt = stmt.limit(limit)
        result = await self.session.exec(stmt)
        return list(result.all())
