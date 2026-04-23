import logging
from pathlib import Path

from asgiref.sync import async_to_sync

from app.celery_app import celery_app
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.redis import create_redis_client
from app.core.tracing import build_llm_config
from app.evaluation.adversarial import AdversarialRunner
from app.evaluation.few_shot_eval import compare_few_shot_performance
from app.intent.service import IntentRecognitionService
from app.tasks.tracing_setup import setup_celery_langsmith_tracing

logger = logging.getLogger(__name__)


async def _run_few_shot_evaluation() -> dict:
    setup_celery_langsmith_tracing()
    llm = create_llm(
        settings.LLM_MODEL,
        temperature=0.0,
        default_config=build_llm_config(
            agent_name="few_shot_evaluator", tags=["evaluation", "internal"]
        ),
    )
    return await compare_few_shot_performance(llm)


@celery_app.task(bind=True, name="evaluation.run_few_shot_evaluation")
def run_few_shot_evaluation(_self) -> dict:
    return async_to_sync(_run_few_shot_evaluation)()


async def _run_adversarial_suite(triggered_by: str = "scheduled") -> dict:
    """Run the adversarial test suite and store results.

    Args:
        triggered_by: Origin of the run ("scheduled" or "manual").

    Returns:
        dict with summary of the run.
    """
    setup_celery_langsmith_tracing()
    dataset_path = Path("data/adversarial_test_cases.jsonl")
    if not dataset_path.exists():
        logger.warning("Adversarial dataset not found at %s", dataset_path)
        return {"error": "Dataset not found", "path": str(dataset_path)}

    redis_client = create_redis_client()
    try:
        llm = create_llm(
            settings.LLM_MODEL,
            temperature=0.0,
            default_config=build_llm_config(
                agent_name="adversarial_runner", tags=["evaluation", "adversarial", "internal"]
            ),
        )
        intent_service = IntentRecognitionService(llm=llm, redis_client=redis_client)
        runner = AdversarialRunner(intent_service=intent_service)
        report = await runner.run(dataset_path)

        from app.core.database import async_session_maker
        from app.models.evaluation import AdversarialTestRun

        async with async_session_maker() as session:
            run_record = AdversarialTestRun(
                total_cases=report.total_cases,
                passed_cases=report.passed_cases,
                failed_cases=report.failed_cases,
                pass_rate=report.pass_rate,
                category_breakdown=report.category_breakdown,
                severity_breakdown=report.severity_breakdown,
                triggered_by=triggered_by,
            )
            session.add(run_record)
            await session.commit()

        return {
            "run_id": run_record.id,
            "total_cases": report.total_cases,
            "passed_cases": report.passed_cases,
            "failed_cases": report.failed_cases,
            "pass_rate": report.pass_rate,
            "triggered_by": triggered_by,
        }
    finally:
        await redis_client.aclose()


@celery_app.task(bind=True, name="evaluation.run_adversarial_suite")
def run_adversarial_suite(_self, triggered_by: str = "scheduled") -> dict:
    return async_to_sync(_run_adversarial_suite)(triggered_by)
