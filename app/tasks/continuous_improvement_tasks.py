import asyncio
import logging
from pathlib import Path

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.services.continuous_improvement import ContinuousImprovementService, RootCause

logger = logging.getLogger(__name__)


def _auto_assign_root_cause(sample) -> RootCause:
    """Heuristic root cause assignment based on sample metrics."""
    if sample.confidence_score is not None and sample.confidence_score < 0.5:
        return RootCause.HALLUCINATION
    if sample.needs_human_transfer:
        return RootCause.INTENT_ERROR
    return RootCause.OTHER


async def _run_weekly_audit() -> dict:
    async with async_session_maker() as session:
        service = ContinuousImprovementService(db_session=session)
        batch = await service.run_audit(days=7, sample_rate=0.05)

        # Auto-assign root causes via heuristics
        for sample in batch.samples:
            if sample.root_cause is None:
                sample.root_cause = _auto_assign_root_cause(sample)

        # Auto-merge into golden dataset
        dataset_path = Path("data/golden_dataset_v2.jsonl")
        if dataset_path.exists() and batch.samples:
            ContinuousImprovementService.merge_feedback_into_dataset(
                dataset_path=dataset_path,
                audit_batch=batch,
            )
            logger.info("Auto-merged %d audit samples into golden dataset", len(batch.samples))

        return {
            "week_start": batch.week_start,
            "total_conversations": batch.total_conversations,
            "sample_size": batch.sample_size,
            "merged_samples": len(batch.samples),
        }


@celery_app.task(bind=True, name="continuous_improvement.run_weekly_audit")
def run_weekly_audit(_self) -> dict:
    return asyncio.run(_run_weekly_audit())
