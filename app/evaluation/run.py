"""CLI entrypoint for running evaluation against the golden dataset."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evaluation.baseline import (
    compare_metrics,
    format_comparison,
    load_baseline,
)
from app.evaluation.pipeline import EvaluationPipeline

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _save_results(results: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"eval_{timestamp}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Results saved to %s", output_path)
    return output_path


async def _init_evaluation_dependencies() -> tuple[Any, Any, Any]:
    """Initialize LLM, intent service, and graph for evaluation.

    Returns:
        Tuple of (intent_service, llm, graph).
    """
    from langgraph.checkpoint.redis import AsyncRedisSaver

    from app.agents.account import AccountAgent
    from app.agents.cart import CartAgent
    from app.agents.complaint import ComplaintAgent
    from app.agents.evaluator import ConfidenceEvaluator
    from app.agents.logistics import LogisticsAgent
    from app.agents.order import OrderAgent
    from app.agents.payment import PaymentAgent
    from app.agents.policy import PolicyAgent
    from app.agents.product import ProductAgent
    from app.agents.router import IntentRouterAgent
    from app.agents.supervisor import SupervisorAgent
    from app.core.config import settings
    from app.core.llm_factory import create_openai_llm
    from app.core.redis import create_redis_client
    from app.core.tracing import build_llm_config
    from app.graph.workflow import compile_app_graph
    from app.intent.service import IntentRecognitionService
    from app.memory.structured_manager import StructuredMemoryManager
    from app.memory.vector_manager import VectorMemoryManager
    from app.retrieval import create_retriever
    from app.services.order_service import OrderService
    from app.tools import (
        AccountTool,
        CartTool,
        ComplaintTool,
        LogisticsTool,
        PaymentTool,
        ProductTool,
    )
    from app.tools.registry import ToolRegistry

    redis_client = create_redis_client()
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    await checkpointer.setup()

    llm = create_openai_llm(
        default_config=build_llm_config(
            agent_name="evaluation_runner", tags=["evaluation", "internal"]
        )
    )
    eval_llm = create_openai_llm(
        model=settings.CONFIDENCE.EVALUATION_MODEL,
        default_config=build_llm_config(
            agent_name="evaluation_runner_eval", tags=["evaluation", "internal", "confidence_eval"]
        ),
    )
    intent_service = IntentRecognitionService(llm=llm, redis_client=redis_client)
    structured_manager = StructuredMemoryManager()
    router_agent = IntentRouterAgent(
        intent_service=intent_service, llm=llm, structured_manager=structured_manager
    )
    retriever = create_retriever(llm=llm, redis_client=redis_client)

    tool_registry = ToolRegistry()
    tool_registry.register(LogisticsTool())
    tool_registry.register(AccountTool())
    tool_registry.register(PaymentTool())
    tool_registry.register(ProductTool(rewriter=retriever.rewriter))
    tool_registry.register(CartTool())
    tool_registry.register(ComplaintTool())

    policy_agent = PolicyAgent(retriever=retriever, llm=llm)
    order_agent = OrderAgent(order_service=OrderService(), llm=llm)
    logistics_agent = LogisticsAgent(tool_registry=tool_registry, llm=llm)
    account_agent = AccountAgent(tool_registry=tool_registry, llm=llm)
    payment_agent = PaymentAgent(tool_registry=tool_registry, llm=llm)
    product_agent = ProductAgent(tool_registry=tool_registry, llm=llm)
    cart_agent = CartAgent(tool_registry=tool_registry, llm=llm)
    complaint_agent = ComplaintAgent(llm=llm)
    supervisor_agent = SupervisorAgent(llm=llm)
    evaluator = ConfidenceEvaluator(llm=eval_llm)
    vector_manager = VectorMemoryManager()

    graph = await compile_app_graph(
        router_agent=router_agent,
        policy_agent=policy_agent,
        order_agent=order_agent,
        logistics_agent=logistics_agent,
        account_agent=account_agent,
        payment_agent=payment_agent,
        evaluator=evaluator,
        checkpointer=checkpointer,
        supervisor_agent=supervisor_agent,
        product_agent=product_agent,
        cart_agent=cart_agent,
        complaint_agent=complaint_agent,
        llm=llm,
        vector_manager=vector_manager,
    )

    return intent_service, llm, graph


async def _run_evaluation(
    dataset_path: str,
    output_dir: Path | None = None,
    baseline_path: str | None = None,
    threshold: float = 0.05,
) -> dict[str, Any]:
    """Run evaluation pipeline and optionally compare against baseline.

    Args:
        dataset_path: Path to the golden dataset JSONL file.
        output_dir: Optional directory to save evaluation results.
        baseline_path: Optional path to baseline JSON for comparison.
        threshold: Maximum allowed degradation ratio (default 0.05 = 5%).

    Returns:
        Evaluation results dictionary.
    """
    intent_service, llm, graph = await _init_evaluation_dependencies()

    pipeline = EvaluationPipeline(
        intent_service=intent_service,
        llm=llm,
        graph=graph,
    )

    results = await pipeline.run(dataset_path)

    if output_dir is not None:
        output_path = _save_results(results, output_dir)
        results["output_path"] = str(output_path)

    if baseline_path is not None:
        baseline = load_baseline(baseline_path)
        comparison = compare_metrics(results, baseline, threshold=threshold)
        results["comparison"] = {
            "passed": comparison.passed,
            "threshold": comparison.threshold,
            "metrics": {
                name: {
                    "baseline": m.baseline,
                    "current": m.current,
                    "degradation": m.degradation,
                    "passed": m.passed,
                }
                for name, m in comparison.metrics.items()
            },
        }
        logger.info("Baseline comparison:\n%s", format_comparison(comparison))
        if not comparison.passed:
            logger.error("Evaluation failed: metrics degraded beyond threshold")
            sys.exit(1)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation against golden dataset")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to golden dataset JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory to save evaluation results (default: reports)",
    )
    parser.add_argument(
        "--baseline",
        help="Path to baseline JSON file for comparison",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Degradation threshold (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        results = asyncio.run(
            _run_evaluation(
                dataset_path=args.dataset,
                output_dir=output_dir,
                baseline_path=args.baseline,
                threshold=args.threshold,
            )
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        sys.exit(1)
    except OSError:
        logger.exception("Evaluation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
