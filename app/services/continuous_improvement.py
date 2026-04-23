"""Continuous improvement service for automated quality audits."""

from __future__ import annotations

import json
import logging
import random
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.evaluation.dataset import GoldenDataset, GoldenRecord, load_golden_dataset
from app.models.observability import GraphExecutionLog

logger = logging.getLogger(__name__)


class RootCause(str, Enum):
    INTENT_ERROR = "intent_error"
    HALLUCINATION = "hallucination"
    LATENCY = "latency"
    SAFETY = "safety"
    TONE = "tone"
    OTHER = "other"


class AuditSample(BaseModel):
    thread_id: str
    user_id: int
    intent_category: str | None
    final_agent: str | None
    confidence_score: float | None
    needs_human_transfer: bool
    created_at: datetime
    query: str = ""
    root_cause: RootCause | None = None
    notes: str | None = None


class AuditBatch(BaseModel):
    week_start: str
    total_conversations: int
    sample_size: int
    samples: list[AuditSample]
    created_at: datetime = datetime.now(UTC)


class ContinuousImprovementService:
    """Service for automated quality audits and golden dataset updates."""

    DEFAULT_SAMPLE_RATE = 0.05
    DEFAULT_AUDIT_DAYS = 7

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sample_conversations(
        self,
        days: int = DEFAULT_AUDIT_DAYS,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
        stratify_by_intent: bool = True,
    ) -> AuditBatch:
        """Sample conversations for quality audit.

        Args:
            days: Number of days to look back.
            sample_rate: Fraction of conversations to sample (0.0-1.0).
            stratify_by_intent: Whether to stratify sampling by intent category.

        Returns:
            AuditBatch with sampled conversations.
        """
        since = datetime.now(UTC) - timedelta(days=days)

        stmt = (
            select(GraphExecutionLog)
            .where(GraphExecutionLog.created_at >= since)  # type: ignore
            .order_by(func.random())
        )
        result = await self.db_session.exec(stmt)  # type: ignore
        all_logs = [row[0] for row in result.all()]

        total = len(all_logs)
        target_size = max(1, int(total * sample_rate))

        if stratify_by_intent and total > 0:
            by_intent: dict[str, list[GraphExecutionLog]] = {}
            for log in all_logs:
                intent = log.intent_category or "unknown"
                by_intent.setdefault(intent, []).append(log)

            samples: list[GraphExecutionLog] = []
            per_intent_target = max(1, target_size // len(by_intent))

            for intent_logs in by_intent.values():
                intent_sample_size = min(per_intent_target, len(intent_logs))
                samples.extend(random.sample(intent_logs, intent_sample_size))

            if len(samples) < target_size:
                remaining = [log for log in all_logs if log not in samples]
                needed = target_size - len(samples)
                if remaining and needed > 0:
                    samples.extend(random.sample(remaining, min(needed, len(remaining))))
        else:
            samples = random.sample(all_logs, min(target_size, total)) if total > 0 else []

        return AuditBatch(
            week_start=since.isoformat(),
            total_conversations=total,
            sample_size=len(samples),
            samples=[
                AuditSample(
                    thread_id=log.thread_id,
                    user_id=log.user_id,
                    intent_category=log.intent_category,
                    final_agent=log.final_agent,
                    confidence_score=log.confidence_score,
                    needs_human_transfer=log.needs_human_transfer,
                    created_at=log.created_at,
                    query=log.query or "",
                )
                for log in samples
            ],
        )

    async def run_audit(
        self,
        days: int = DEFAULT_AUDIT_DAYS,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
    ) -> AuditBatch:
        """Run a full quality audit and log results.

        Args:
            days: Number of days to look back.
            sample_rate: Fraction of conversations to sample.

        Returns:
            AuditBatch with results.
        """
        batch = await self.sample_conversations(days=days, sample_rate=sample_rate)
        logger.info(
            "Audit complete: sampled %d/%d conversations for week starting %s",
            batch.sample_size,
            batch.total_conversations,
            batch.week_start,
        )
        return batch

    @staticmethod
    def merge_feedback_into_dataset(
        dataset_path: str | Path,
        audit_batch: AuditBatch,
        output_path: str | Path | None = None,
    ) -> GoldenDataset:
        """Merge audit feedback into the golden dataset.

        Adds new records from audit samples with root cause annotations,
        avoiding duplicates by thread_id.

        Args:
            dataset_path: Path to existing golden dataset.
            audit_batch: Audit batch with samples to merge.
            output_path: Optional path to save updated dataset. If None, overwrites input.

        Returns:
            Updated GoldenDataset.
        """
        dataset = load_golden_dataset(dataset_path)
        existing_thread_ids = {
            r.query.replace("[AUDIT] ", "").replace("thread=", "").strip()
            for r in dataset.records
            if r.query.strip().startswith("[AUDIT]")
        }
        existing_queries = {r.query.strip() for r in dataset.records}

        dimension_map = {
            RootCause.INTENT_ERROR: "ambiguous_intent",
            RootCause.HALLUCINATION: "abnormal_input",
            RootCause.LATENCY: "long_conversation",
            RootCause.SAFETY: "abnormal_input",
            RootCause.TONE: "abnormal_input",
            RootCause.OTHER: "abnormal_input",
        }

        new_records: list[GoldenRecord] = []
        for sample in audit_batch.samples:
            if not sample.root_cause:
                continue
            query_text = sample.query if sample.query else f"[AUDIT] thread={sample.thread_id}"
            if query_text in existing_queries:
                continue
            if sample.thread_id in existing_thread_ids:
                continue
            query_text = sample.query if sample.query else f"[AUDIT] thread={sample.thread_id}"
            new_records.append(
                GoldenRecord(
                    query=query_text,
                    expected_intent=sample.intent_category or "OTHER",
                    expected_slots={},
                    expected_answer_fragment=f"Audit: {sample.root_cause.value if sample.root_cause else 'unknown'}",
                    expected_audit_level="medium",
                    dimension=dimension_map.get(sample.root_cause, "abnormal_input"),
                )
            )

        if new_records:
            dataset.records.extend(new_records)
            dataset.source_path = str(output_path or dataset_path)

            output = Path(output_path or dataset_path)
            with output.open("w", encoding="utf-8") as f:
                for record in dataset.records:
                    f.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

            logger.info(
                "Merged %d new records into dataset. Total: %d",
                len(new_records),
                dataset.total_records,
            )
        else:
            logger.info("No new records to merge into dataset.")

        return dataset
