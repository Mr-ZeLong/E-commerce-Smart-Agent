"""Shadow testing service for comparing production vs new models/prompts."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ShadowComparisonResult:
    thread_id: str
    production_intent: str | None
    shadow_intent: str | None
    intent_match: bool
    production_answer: str
    shadow_answer: str
    answer_similarity: float
    production_latency_ms: int
    shadow_latency_ms: int
    latency_delta_ms: int
    timestamp: datetime


@dataclass
class ShadowReport:
    total_comparisons: int
    intent_match_rate: float
    avg_answer_similarity: float
    avg_latency_delta_ms: float
    latency_regression: bool
    results: list[ShadowComparisonResult]


class ShadowOrchestrator:
    """Orchestrates shadow testing by running production and shadow versions in parallel."""

    def __init__(self, sample_rate: float = 0.1):
        self.sample_rate = sample_rate

    def should_sample(self, thread_id: str) -> bool:
        """Determine if a given thread should be shadow-tested.

        Uses a deterministic hash of the thread_id to ensure consistent
        sampling without external state.
        """
        hash_val = hash(thread_id) & 0xFFFFFFFF
        return (hash_val / 0xFFFFFFFF) < self.sample_rate

    @staticmethod
    async def run_shadow(
        query: str,
        production_graph: Any,
        shadow_graph: Any,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run both production and shadow graphs on the same query.

        Args:
            query: User query to process.
            production_graph: The production graph to invoke.
            shadow_graph: The shadow graph to invoke.
            session_id: Optional session ID.

        Returns:
            Tuple of (production_result, shadow_result).
        """
        sid = session_id or f"shadow-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": sid}}

        import time

        prod_start = time.time()
        prod_result = await production_graph.ainvoke({"question": query}, config)
        prod_latency = int((time.time() - prod_start) * 1000)

        shadow_start = time.time()
        shadow_result = await shadow_graph.ainvoke({"question": query}, config)
        shadow_latency = int((time.time() - shadow_start) * 1000)

        return (
            {"result": prod_result, "latency_ms": prod_latency},
            {"result": shadow_result, "latency_ms": shadow_latency},
        )

    @staticmethod
    def compare_results(
        thread_id: str,
        production_result: dict[str, Any],
        shadow_result: dict[str, Any],
    ) -> ShadowComparisonResult:
        """Compare production and shadow results.

        Args:
            thread_id: The conversation thread ID.
            production_result: Production graph output with 'result' and 'latency_ms'.
            shadow_result: Shadow graph output with 'result' and 'latency_ms'.

        Returns:
            ShadowComparisonResult with detailed comparison.
        """
        prod_data = production_result["result"]
        shadow_data = shadow_result["result"]

        prod_intent = prod_data.get("intent_category")
        shadow_intent = shadow_data.get("intent_category")
        intent_match = prod_intent == shadow_intent

        prod_answer = prod_data.get("answer", "")
        shadow_answer = shadow_data.get("answer", "")
        similarity = _answer_similarity(prod_answer, shadow_answer)

        prod_latency = production_result["latency_ms"]
        shadow_latency = shadow_result["latency_ms"]

        return ShadowComparisonResult(
            thread_id=thread_id,
            production_intent=prod_intent,
            shadow_intent=shadow_intent,
            intent_match=intent_match,
            production_answer=prod_answer,
            shadow_answer=shadow_answer,
            answer_similarity=similarity,
            production_latency_ms=prod_latency,
            shadow_latency_ms=shadow_latency,
            latency_delta_ms=shadow_latency - prod_latency,
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def generate_report(results: list[ShadowComparisonResult]) -> ShadowReport:
        """Generate an aggregate shadow testing report.

        Args:
            results: List of comparison results.

        Returns:
            ShadowReport with aggregated metrics.
        """
        if not results:
            return ShadowReport(
                total_comparisons=0,
                intent_match_rate=0.0,
                avg_answer_similarity=0.0,
                avg_latency_delta_ms=0.0,
                latency_regression=False,
                results=[],
            )

        total = len(results)
        intent_matches = sum(1 for r in results if r.intent_match)
        avg_similarity = sum(r.answer_similarity for r in results) / total
        avg_latency_delta = sum(r.latency_delta_ms for r in results) / total
        latency_regression = avg_latency_delta > 500

        return ShadowReport(
            total_comparisons=total,
            intent_match_rate=intent_matches / total,
            avg_answer_similarity=avg_similarity,
            avg_latency_delta_ms=avg_latency_delta,
            latency_regression=latency_regression,
            results=results,
        )


def _answer_similarity(answer1: str, answer2: str) -> float:
    """Compute a simple similarity score between two answers.

    Uses Jaccard similarity on word sets.
    """
    if not answer1 and not answer2:
        return 1.0
    if not answer1 or not answer2:
        return 0.0

    words1 = set(answer1.lower().split())
    words2 = set(answer2.lower().split())

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0
