"""Performance regression tests for E-commerce Smart Agent.

These tests measure latencies of critical paths and enforce SLOs:
- P95 latency < 500ms for retrieval and memory operations
- P99 latency < 1000ms for end-to-end chat

Run with: uv run pytest tests/performance/ -v
"""

import asyncio
import statistics
import time
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client import models

from app.core.cache import CacheManager
from app.graph.nodes import build_memory_node
from app.memory.structured_manager import StructuredMemoryManager
from app.memory.vector_manager import VectorMemoryManager
from app.models.state import make_agent_state
from app.retrieval.retriever import HybridRetriever

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


class _Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start) * 1000


def _percentile(values: list[float], p: float) -> float:
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_vals) else f
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


# --------------------------------------------------------------------------- #
# Retrieval performance
# --------------------------------------------------------------------------- #


class FastDenseEmbedder:
    async def aembed_query(self, text: str) -> list[float]:
        await asyncio.sleep(0.005)  # 5ms simulated latency
        return [0.1] * 1024


class FastSparseEmbedder:
    async def aembed(self, texts: list[str]) -> list[models.SparseVector]:
        await asyncio.sleep(0.005)  # 5ms simulated latency
        return [models.SparseVector(indices=[0, 1], values=[1.0, 0.5]) for _ in texts]


class FastReranker:
    async def rerank(self, query: str, documents: list[str], top_n: int = 5):
        await asyncio.sleep(0.002)
        from app.retrieval.reranker import RerankResult

        return [
            RerankResult(index=i, score=0.99 - i * 0.01) for i in range(min(top_n, len(documents)))
        ]


class FastRewriter:
    async def rewrite(self, query: str, **kwargs: Any) -> str:
        return query

    async def rewrite_multi(self, query: str, **kwargs: Any) -> list[str]:
        return [query]


class MockQdrantClient:
    async def query_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        dense_limit: int = 15,
        sparse_limit: int = 15,
        limit: int = 10,
    ) -> list[models.ScoredPoint]:
        await asyncio.sleep(0.01)  # 10ms Qdrant latency
        return [
            models.ScoredPoint(
                id=1,
                version=1,
                score=0.95,
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
            models.ScoredPoint(
                id=2,
                version=1,
                score=0.90,
                payload={"content": "c2", "source": "s2", "meta_data": {}},
            ),
        ]


@pytest.mark.asyncio
async def test_retrieval_p95_under_100ms() -> None:
    """Hybrid retrieval with parallel embeddings should complete in <100ms P95."""
    retriever = HybridRetriever(
        qdrant_client=MockQdrantClient(),
        dense_embedder=FastDenseEmbedder(),
        sparse_embedder=FastSparseEmbedder(),
        reranker=FastReranker(),
        rewriter=FastRewriter(),
    )

    latencies: list[float] = []
    for _ in range(20):
        with _Timer() as t:
            results = await retriever.retrieve("test query")
        latencies.append(t.elapsed_ms)
        assert len(results) > 0

    p95 = _percentile(latencies, 0.95)
    print(f"Retrieval P95: {p95:.2f}ms (samples={len(latencies)})")
    assert p95 < 100.0, f"Retrieval P95 {p95:.2f}ms exceeds 100ms budget"


# --------------------------------------------------------------------------- #
# Memory node performance
# --------------------------------------------------------------------------- #


class MockStructuredManager:
    async def get_user_profile(self, session: Any, user_id: int) -> Any:
        await asyncio.sleep(0.003)
        return MagicMock(
            user_id=user_id,
            membership_level="gold",
            preferred_language="zh",
            timezone="Asia/Shanghai",
            total_orders=10,
            lifetime_value=5000.0,
        )

    async def get_user_preferences(self, session: Any, user_id: int) -> list[Any]:
        await asyncio.sleep(0.003)
        return []

    async def get_user_facts(self, session: Any, user_id: int, limit: int = 3) -> list[Any]:
        await asyncio.sleep(0.003)
        return []

    async def get_recent_summaries(self, session: Any, user_id: int, limit: int = 2) -> list[Any]:
        await asyncio.sleep(0.003)
        return []


class MockVectorManager:
    async def search_similar(
        self,
        user_id: int,
        query_text: str,
        top_k: int = 5,
        message_role: str | None = None,
    ) -> list[dict[str, Any]]:
        await asyncio.sleep(0.005)
        return []


@pytest.mark.asyncio
async def test_memory_node_p95_under_50ms() -> None:
    """Memory node with parallel queries should complete in <50ms P95."""
    node = build_memory_node(
        structured_manager=cast(StructuredMemoryManager, MockStructuredManager()),
        vector_manager=cast(VectorMemoryManager, MockVectorManager()),
    )
    state = make_agent_state(
        question="test",
        user_id=1,
        thread_id="t1",
        history=[{"role": "user", "content": "test"}],
    )

    latencies: list[float] = []
    for _ in range(20):
        with _Timer() as t:
            result = await node(state)
        latencies.append(t.elapsed_ms)
        assert isinstance(result.update, dict)
        assert "memory_context" in result.update

    p95 = _percentile(latencies, 0.95)
    print(f"Memory node P95: {p95:.2f}ms (samples={len(latencies)})")
    assert p95 < 50.0, f"Memory node P95 {p95:.2f}ms exceeds 50ms budget"


# --------------------------------------------------------------------------- #
# Cache performance
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_cache_reduces_latency(redis_client: Any) -> None:
    """Cached structured memory lookups should be faster than DB hits."""
    cache = CacheManager(redis_client)
    manager = StructuredMemoryManager(cache_manager=cache)

    # We don't have a real DB session in this test; mock the session method
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec.return_value = mock_result

    # First call (cache miss)
    t1_start = time.perf_counter()
    await manager.get_user_profile(mock_session, user_id=42)
    t1_ms = (time.perf_counter() - t1_start) * 1000

    # Second call (cache hit)
    t2_start = time.perf_counter()
    await manager.get_user_profile(mock_session, user_id=42)
    t2_ms = (time.perf_counter() - t2_start) * 1000

    print(f"Cache miss: {t1_ms:.2f}ms, Cache hit: {t2_ms:.2f}ms")
    assert t2_ms < t1_ms, "Cache hit should be faster than cache miss"


# --------------------------------------------------------------------------- #
# End-to-end chat latency (mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_chat_endpoint_p95_under_500ms(client: Any) -> None:
    """Chat endpoint with mocked graph should respond in <500ms P95.

    This test uses a mocked graph to isolate API-layer latency from LLM latency.
    """
    from app.core.security import get_current_user_id
    from app.main import app

    # Mock auth dependency to avoid 401
    async def _mock_get_current_user_id():
        return 999

    app.dependency_overrides[get_current_user_id] = _mock_get_current_user_id

    # Mock the graph to avoid real LLM calls
    mock_graph = MagicMock()

    async def _fast_astream_events(state: Any, config: Any, version: str):
        await asyncio.sleep(0.05)  # 50ms simulated graph latency
        yield {
            "event": "on_chain_end",
            "data": {"output": {"answer": "mock answer"}},
            "metadata": {"langgraph_node": "policy_agent"},
            "run_id": "r1",
        }

    mock_graph.astream_events = _fast_astream_events
    original_graph = getattr(app.state, "app_graph", None)
    original_intent = getattr(app.state, "intent_service", None)
    original_vector = getattr(app.state, "vector_manager", None)
    original_cache = getattr(app.state, "cache_manager", None)

    app.state.app_graph = mock_graph
    app.state.intent_service = MagicMock()
    app.state.intent_service.recognize = AsyncMock(
        return_value=MagicMock(primary_intent=MagicMock(value="POLICY"))
    )
    app.state.vector_manager = None
    app.state.cache_manager = None

    try:
        latencies: list[float] = []
        for _ in range(20):
            with _Timer() as t:
                response = await client.post(
                    "/api/v1/chat",
                    json={"question": "test question", "thread_id": "perf-t1"},
                )
            latencies.append(t.elapsed_ms)
            assert response.status_code == 200

        p95 = _percentile(latencies, 0.95)
        p99 = _percentile(latencies, 0.99)
        mean = statistics.mean(latencies)
        print(
            f"Chat endpoint mean={mean:.2f}ms P95={p95:.2f}ms P99={p99:.2f}ms "
            f"(samples={len(latencies)})"
        )
        assert p95 < 500.0, f"Chat P95 {p95:.2f}ms exceeds 500ms SLO"
        assert p99 < 1000.0, f"Chat P99 {p99:.2f}ms exceeds 1000ms SLO"
    finally:
        app.state.app_graph = original_graph
        app.state.intent_service = original_intent
        app.state.vector_manager = original_vector
        app.state.cache_manager = original_cache
        app.dependency_overrides.clear()
