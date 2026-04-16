import asyncio
import logging

from app.celery_app import celery_app
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.evaluation.few_shot_eval import compare_few_shot_performance

logger = logging.getLogger(__name__)


async def _run_few_shot_evaluation() -> dict:
    llm = create_llm(settings.LLM_MODEL, temperature=0.0)
    return await compare_few_shot_performance(llm)


@celery_app.task(bind=True, name="evaluation.run_few_shot_evaluation")
def run_few_shot_evaluation(_self) -> dict:
    return asyncio.run(_run_few_shot_evaluation())
