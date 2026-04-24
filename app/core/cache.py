"""Redis-backed caching layer for hot queries.

Provides a ``CacheManager`` that handles caching for:
- Intent recognition results
- User profile lookups
- Retrieval results

All operations are async and include Prometheus metrics.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.observability.metrics import (
    record_cache_hit,
    record_cache_miss,
    record_redis_connection_error,
    record_redis_operation_latency,
    set_cache_hit_ratio,
)

logger = logging.getLogger(__name__)


class CacheManager:
    """Async cache manager backed by Redis.

    Tracks hit/miss ratios per cache name and exports them as Prometheus
    metrics.  All Redis operations are wrapped with latency observation.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis
        self._stats: dict[str, dict[str, int]] = {
            "intent": {"hits": 0, "misses": 0},
            "profile": {"hits": 0, "misses": 0},
            "retrieval": {"hits": 0, "misses": 0},
            "facts": {"hits": 0, "misses": 0},
            "preferences": {"hits": 0, "misses": 0},
            "summaries": {"hits": 0, "misses": 0},
            "vector_search": {"hits": 0, "misses": 0},
        }

    # ------------------------------------------------------------------ #
    # Generic helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hash_key(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _record_hit(self, cache_name: str) -> None:
        self._stats[cache_name]["hits"] += 1
        record_cache_hit(cache_name)
        self._maybe_update_ratio(cache_name)

    def _record_miss(self, cache_name: str) -> None:
        self._stats[cache_name]["misses"] += 1
        record_cache_miss(cache_name)
        self._maybe_update_ratio(cache_name)

    def _maybe_update_ratio(self, cache_name: str) -> None:
        stats = self._stats[cache_name]
        total = stats["hits"] + stats["misses"]
        if total > 0 and total % 10 == 0:
            ratio = stats["hits"] / total
            set_cache_hit_ratio(cache_name, ratio)

    async def _redis_get(self, key: str) -> str | None:
        start = time.perf_counter()
        try:
            value = await self.redis.get(key)
            record_redis_operation_latency("get", time.perf_counter() - start)
            return value if value is None else str(value)
        except aioredis.RedisError as exc:
            record_redis_operation_latency("get", time.perf_counter() - start)
            record_redis_connection_error(type(exc).__name__.lower())
            logger.warning("Redis GET failed for %s: %s", key, exc)
            return None

    async def _redis_set(
        self,
        key: str,
        value: str,
        ttl: int,
    ) -> None:
        start = time.perf_counter()
        try:
            await self.redis.setex(key, ttl, value)
            record_redis_operation_latency("set", time.perf_counter() - start)
        except aioredis.RedisError as exc:
            record_redis_operation_latency("set", time.perf_counter() - start)
            record_redis_connection_error(type(exc).__name__.lower())
            logger.warning("Redis SET failed for %s: %s", key, exc)

    async def _redis_delete(self, key: str) -> None:
        start = time.perf_counter()
        try:
            await self.redis.delete(key)
            record_redis_operation_latency("delete", time.perf_counter() - start)
        except aioredis.RedisError as exc:
            record_redis_operation_latency("delete", time.perf_counter() - start)
            record_redis_connection_error(type(exc).__name__.lower())
            logger.warning("Redis DELETE failed for %s: %s", key, exc)

    async def _redis_delete_pattern(self, pattern: str) -> None:
        start = time.perf_counter()
        try:
            keys: list[str] = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self.redis.delete(*keys)
            record_redis_operation_latency("delete_pattern", time.perf_counter() - start)
        except aioredis.RedisError as exc:
            record_redis_operation_latency("delete_pattern", time.perf_counter() - start)
            record_redis_connection_error(type(exc).__name__.lower())
            logger.warning("Redis DELETE pattern failed for %s: %s", pattern, exc)

    # ------------------------------------------------------------------ #
    # Intent cache
    # ------------------------------------------------------------------ #

    async def get_intent(self, query: str) -> dict[str, Any] | None:
        """Fetch a cached intent result for *query*.

        Returns:
            Parsed JSON dict or ``None`` if not cached or on error.
        """
        key = f"intent:{self._hash_key(query)}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("intent")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted intent cache for key %s", key)
        self._record_miss("intent")
        return None

    async def set_intent(self, query: str, result: dict[str, Any]) -> None:
        """Cache an intent result for *query*."""
        key = f"intent:{self._hash_key(query)}"
        await self._redis_set(
            key, json.dumps(result, ensure_ascii=False), settings.CACHE_TTL_INTENT
        )

    async def invalidate_intent(self, query: str) -> None:
        """Remove a specific intent cache entry."""
        key = f"intent:{self._hash_key(query)}"
        await self._redis_delete(key)

    # ------------------------------------------------------------------ #
    # Profile cache
    # ------------------------------------------------------------------ #

    async def get_profile(self, user_id: int) -> dict[str, Any] | None:
        """Fetch a cached user profile for *user_id*."""
        key = f"profile:{user_id}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("profile")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted profile cache for key %s", key)
        self._record_miss("profile")
        return None

    async def set_profile(self, user_id: int, profile: dict[str, Any]) -> None:
        """Cache a user profile for *user_id*."""
        key = f"profile:{user_id}"
        await self._redis_set(
            key, json.dumps(profile, ensure_ascii=False), settings.CACHE_TTL_PROFILE
        )

    async def invalidate_profile(self, user_id: int) -> None:
        """Remove a specific profile cache entry."""
        key = f"profile:{user_id}"
        await self._redis_delete(key)

    async def invalidate_all_profiles(self) -> None:
        """Remove all profile cache entries."""
        await self._redis_delete_pattern("profile:*")

    # ------------------------------------------------------------------ #
    # Retrieval cache
    # ------------------------------------------------------------------ #

    async def get_retrieval(self, query: str) -> list[dict[str, Any]] | None:
        """Fetch cached retrieval results for *query*."""
        key = f"retrieval:{self._hash_key(query)}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("retrieval")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted retrieval cache for key %s", key)
        self._record_miss("retrieval")
        return None

    async def set_retrieval(self, query: str, chunks: list[dict[str, Any]]) -> None:
        """Cache retrieval results for *query*."""
        key = f"retrieval:{self._hash_key(query)}"
        await self._redis_set(
            key, json.dumps(chunks, ensure_ascii=False), settings.CACHE_TTL_RETRIEVAL
        )

    async def invalidate_retrieval(self, query: str) -> None:
        """Remove a specific retrieval cache entry."""
        key = f"retrieval:{self._hash_key(query)}"
        await self._redis_delete(key)

    async def invalidate_all_retrieval(self) -> None:
        """Remove all retrieval cache entries."""
        await self._redis_delete_pattern("retrieval:*")

    # ------------------------------------------------------------------ #
    # User facts cache
    # ------------------------------------------------------------------ #

    async def get_facts(
        self, user_id: int, fact_types: list[str] | None = None, limit: int = 3
    ) -> list[dict[str, Any]] | None:
        """Fetch cached user facts for *user_id*."""
        type_hash = self._hash_key(",".join(sorted(fact_types))) if fact_types else "all"
        key = f"facts:{user_id}:{type_hash}:{limit}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("facts")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted facts cache for key %s", key)
        self._record_miss("facts")
        return None

    async def set_facts(
        self,
        user_id: int,
        facts: list[dict[str, Any]],
        fact_types: list[str] | None = None,
        limit: int = 3,
    ) -> None:
        """Cache user facts for *user_id*."""
        type_hash = self._hash_key(",".join(sorted(fact_types))) if fact_types else "all"
        key = f"facts:{user_id}:{type_hash}:{limit}"
        await self._redis_set(
            key, json.dumps(facts, ensure_ascii=False), settings.CACHE_TTL_PROFILE
        )

    async def invalidate_facts(self, user_id: int) -> None:
        """Remove all facts cache entries for *user_id*."""
        await self._redis_delete_pattern(f"facts:{user_id}:*")

    # ------------------------------------------------------------------ #
    # User preferences cache
    # ------------------------------------------------------------------ #

    async def get_preferences(self, user_id: int) -> list[dict[str, Any]] | None:
        """Fetch cached user preferences for *user_id*."""
        key = f"preferences:{user_id}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("preferences")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted preferences cache for key %s", key)
        self._record_miss("preferences")
        return None

    async def set_preferences(self, user_id: int, preferences: list[dict[str, Any]]) -> None:
        """Cache user preferences for *user_id*."""
        key = f"preferences:{user_id}"
        await self._redis_set(
            key, json.dumps(preferences, ensure_ascii=False), settings.CACHE_TTL_PROFILE
        )

    async def invalidate_preferences(self, user_id: int) -> None:
        """Remove preferences cache entry for *user_id*."""
        key = f"preferences:{user_id}"
        await self._redis_delete(key)

    # ------------------------------------------------------------------ #
    # Interaction summaries cache
    # ------------------------------------------------------------------ #

    async def get_summaries(self, user_id: int, limit: int = 2) -> list[dict[str, Any]] | None:
        """Fetch cached interaction summaries for *user_id*."""
        key = f"summaries:{user_id}:{limit}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("summaries")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted summaries cache for key %s", key)
        self._record_miss("summaries")
        return None

    async def set_summaries(
        self, user_id: int, summaries: list[dict[str, Any]], limit: int = 2
    ) -> None:
        """Cache interaction summaries for *user_id*."""
        key = f"summaries:{user_id}:{limit}"
        await self._redis_set(
            key, json.dumps(summaries, ensure_ascii=False), settings.CACHE_TTL_PROFILE
        )

    async def invalidate_summaries(self, user_id: int) -> None:
        """Remove all summaries cache entries for *user_id*."""
        await self._redis_delete_pattern(f"summaries:{user_id}:*")

    # ------------------------------------------------------------------ #
    # Vector search cache
    # ------------------------------------------------------------------ #

    async def get_vector_search(
        self, user_id: int, query_hash: str, top_k: int, message_role: str | None = None
    ) -> list[dict[str, Any]] | None:
        """Fetch cached vector search results."""
        role_suffix = f":{message_role}" if message_role else ":all"
        key = f"vsearch:{user_id}:{query_hash}:{top_k}{role_suffix}"
        data = await self._redis_get(key)
        if data is not None:
            try:
                self._record_hit("vector_search")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Corrupted vector search cache for key %s", key)
        self._record_miss("vector_search")
        return None

    async def set_vector_search(
        self,
        user_id: int,
        query_hash: str,
        top_k: int,
        results: list[dict[str, Any]],
        message_role: str | None = None,
        ttl: int = 300,
    ) -> None:
        """Cache vector search results."""
        role_suffix = f":{message_role}" if message_role else ":all"
        key = f"vsearch:{user_id}:{query_hash}:{top_k}{role_suffix}"
        await self._redis_set(key, json.dumps(results, ensure_ascii=False), ttl)

    async def invalidate_vector_search(self, user_id: int) -> None:
        """Remove all vector search cache entries for *user_id*."""
        await self._redis_delete_pattern(f"vsearch:{user_id}:*")

    # ------------------------------------------------------------------ #
    # Bulk invalidation helpers
    # ------------------------------------------------------------------ #

    async def invalidate_all(self) -> None:
        """Clear all managed caches."""
        await self._redis_delete_pattern("intent:*")
        await self._redis_delete_pattern("profile:*")
        await self._redis_delete_pattern("retrieval:*")
        await self._redis_delete_pattern("facts:*")
        await self._redis_delete_pattern("preferences:*")
        await self._redis_delete_pattern("summaries:*")
        await self._redis_delete_pattern("vsearch:*")
