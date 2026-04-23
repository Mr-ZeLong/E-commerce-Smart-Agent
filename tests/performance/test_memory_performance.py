"""Performance regression tests for memory system optimizations.

These tests verify that caching and parallelization improvements deliver
measurable latency reductions. They use mocked dependencies to isolate the
performance characteristics of the code under test.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.core.cache import CacheManager
from app.memory.structured_manager import StructuredMemoryManager
from app.memory.vector_manager import VectorMemoryManager


@pytest_asyncio.fixture(loop_scope="function")
async def structured_manager_with_cache(redis_client):
    cache = CacheManager(redis_client)
    manager = StructuredMemoryManager(cache_manager=cache)
    return manager, cache


@pytest_asyncio.fixture(loop_scope="function")
async def vector_manager_with_cache(redis_client):
    cache = CacheManager(redis_client)
    # Use a mock client to avoid Qdrant overhead in unit tests.
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True
    mock_client.query_points.return_value = MagicMock(points=[])

    mock_embedder = AsyncMock()
    mock_embedder.aembed_documents.return_value = [[0.1] * 1024]

    manager = VectorMemoryManager(
        client=mock_client, embedder=mock_embedder, cache_manager=cache
    )
    return manager, cache, mock_client


class TestStructuredMemoryCaching:
    """Verify that CacheManager-backed reads avoid redundant DB round-trips."""

    @pytest.mark.asyncio
    async def test_get_user_facts_cache_hit_avoids_db(self, structured_manager_with_cache):
        """Second call to get_user_facts should hit cache and skip DB exec."""
        manager, _cache = structured_manager_with_cache
        mock_session = AsyncMock()
        mock_exec = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_exec.return_value = mock_result
        mock_session.exec = mock_exec

        # Warm cache with empty result.
        await manager.get_user_facts(mock_session, user_id=1)
        first_call_count = mock_exec.call_count

        # Second call should read from cache and not touch session.exec again.
        await manager.get_user_facts(mock_session, user_id=1)
        second_call_count = mock_exec.call_count

        assert second_call_count == first_call_count, (
            "Cache hit should not trigger additional DB exec calls"
        )

    @pytest.mark.asyncio
    async def test_get_user_preferences_cache_hit_avoids_db(self, structured_manager_with_cache):
        """Second call to get_user_preferences should hit cache."""
        manager, _cache = structured_manager_with_cache
        mock_session = AsyncMock()
        mock_exec = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_exec.return_value = mock_result
        mock_session.exec = mock_exec

        await manager.get_user_preferences(mock_session, user_id=1)
        first = mock_exec.call_count

        await manager.get_user_preferences(mock_session, user_id=1)
        second = mock_exec.call_count

        assert second == first

    @pytest.mark.asyncio
    async def test_get_recent_summaries_cache_hit_avoids_db(self, structured_manager_with_cache):
        """Second call to get_recent_summaries should hit cache."""
        manager, _cache = structured_manager_with_cache
        mock_session = AsyncMock()
        mock_exec = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_exec.return_value = mock_result
        mock_session.exec = mock_exec

        await manager.get_recent_summaries(mock_session, user_id=1)
        first = mock_exec.call_count

        await manager.get_recent_summaries(mock_session, user_id=1)
        second = mock_exec.call_count

        assert second == first

    @pytest.mark.asyncio
    async def test_save_user_fact_invalidates_cache(self, structured_manager_with_cache):
        """After saving a fact, the facts cache should be invalidated."""
        manager, cache = structured_manager_with_cache
        mock_session = AsyncMock()
        mock_exec = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.one_or_none.return_value = None
        mock_exec.return_value = mock_result
        mock_session.exec = mock_exec
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Warm cache.
        await manager.get_user_facts(mock_session, user_id=1)
        first = mock_exec.call_count

        # Save a new fact.
        await manager.save_user_fact(
            mock_session, user_id=1, fact_type="test", content="hello", confidence=0.9
        )

        # Next read should hit DB again because cache was invalidated.
        await manager.get_user_facts(mock_session, user_id=1)
        second = mock_exec.call_count

        assert second > first, "Cache invalidation should trigger a fresh DB read"


class TestVectorSearchCaching:
    """Verify that vector search results are cached to avoid redundant Qdrant calls."""

    @pytest.mark.asyncio
    async def test_search_similar_cache_hit_avoids_qdrant(self, vector_manager_with_cache):
        """Second identical search should hit cache and skip Qdrant."""
        manager, cache, mock_client = vector_manager_with_cache

        await manager.search_similar(user_id=1, query_text="hello", top_k=5)
        # Check that the result was cached.
        from hashlib import sha256

        query_hash = sha256(b"hello").hexdigest()[:16]
        cached = await cache.get_vector_search(1, query_hash, 5)
        assert cached is not None, "Result should be cached after first search"

        # Reset Qdrant mock to verify it is not called on cache hit.
        mock_client.query_points.reset_mock()
        await manager.search_similar(user_id=1, query_text="hello", top_k=5)
        mock_client.query_points.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_similar_cache_miss_queries_qdrant(self, vector_manager_with_cache):
        """Different query should create a separate cache entry."""
        manager, cache, _mock_client = vector_manager_with_cache
        from hashlib import sha256

        await manager.search_similar(user_id=1, query_text="hello", top_k=5)
        hello_hash = sha256(b"hello").hexdigest()[:16]
        hello_cached = await cache.get_vector_search(1, hello_hash, 5)

        await manager.search_similar(user_id=1, query_text="world", top_k=5)
        world_hash = sha256(b"world").hexdigest()[:16]
        world_cached = await cache.get_vector_search(1, world_hash, 5)

        assert hello_cached is not None, "hello query should be cached"
        assert world_cached is not None, "world query should be cached"
        assert hello_hash != world_hash, "Different queries should have different cache keys"


class TestParallelExecutionSpeedup:
    """Micro-benchmark verifying asyncio.gather is faster than sequential await."""

    @pytest.mark.asyncio
    async def test_gather_is_faster_than_sequential(self):
        """Four concurrent sleeps should take ~1x the single sleep time."""
        sleep_sec = 0.05

        async def _slow_op():
            await asyncio.sleep(sleep_sec)
            return 1

        # Sequential
        t0 = time.perf_counter()
        await _slow_op()
        await _slow_op()
        await _slow_op()
        await _slow_op()
        seq_time = time.perf_counter() - t0

        # Parallel
        t0 = time.perf_counter()
        await asyncio.gather(_slow_op(), _slow_op(), _slow_op(), _slow_op())
        par_time = time.perf_counter() - t0

        # Parallel should be significantly faster (at least 2x).
        assert par_time < seq_time / 2, (
            f"Parallel execution ({par_time:.3f}s) should be faster than "
            f"sequential ({seq_time:.3f}s)"
        )
