import asyncio
import logging

from app.celery_app import celery_app
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.tracing import build_llm_config
from app.evaluation.few_shot_eval import compare_few_shot_performance
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
    return asyncio.run(_run_few_shot_evaluation())
