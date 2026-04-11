import asyncio
import json
import sys

from fastapi import FastAPI

from app.core.config import settings
from app.evaluation.pipeline import EvaluationPipeline
from app.main import lifespan


async def main() -> int:
    if settings.OPENAI_API_KEY in ("", "sk-test") or "localhost" in settings.OPENAI_BASE_URL:
        print(
            json.dumps(
                {
                    "skipped": True,
                    "reason": "No real LLM endpoint available; skipping full evaluation pipeline run.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    app = FastAPI(lifespan=lifespan)
    async with lifespan(app):
        pipeline = EvaluationPipeline(
            intent_service=app.state.intent_service,
            llm=app.state.llm,
            graph=app.state.app_graph,
        )
        results = await pipeline.run("tests/evaluation/golden_dataset_v1.jsonl")
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
