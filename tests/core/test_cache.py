"""Tests for CacheManager."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis

from app.core.cache import CacheManager


def _make_async_iter(items):
    """Return an async generator that yields *items*."""

    async def _scan_iter(*args, **kwargs):
        for item in items:
            yield item

    return _scan_iter


@pytest.fixture
def mock_redis():
    redis = MagicMock(spec=aioredis.Redis)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.scan_iter = _make_async_iter([])
    return redis


@pytest.fixture
def cache_manager(mock_redis):
    return CacheManager(mock_redis)


class TestCacheManagerIntent:
    @pytest.mark.asyncio
    async def test_get_intent_cache_hit(self, cache_manager, mock_redis):
        intent_data = {"primary_intent": "ORDER", "confidence": 0.9}
        mock_redis.get = AsyncMock(return_value=json.dumps(intent_data))
        result = await cache_manager.get_intent("查询订单")
        assert result == intent_data
        assert cache_manager._stats["intent"]["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_intent_cache_miss(self, cache_manager, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await cache_manager.get_intent("查询订单")
        assert result is None
        assert cache_manager._stats["intent"]["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_intent_corrupted_cache(self, cache_manager, mock_redis):
        mock_redis.get = AsyncMock(return_value="not-json")
        result = await cache_manager.get_intent("查询订单")
        assert result is None
        assert cache_manager._stats["intent"]["misses"] == 1

    @pytest.mark.asyncio
    async def test_set_intent(self, cache_manager, mock_redis):
        intent_data = {"primary_intent": "ORDER", "confidence": 0.9}
        await cache_manager.set_intent("查询订单", intent_data)
        mock_redis.setex.assert_called_once()
        key = mock_redis.setex.call_args[0][0]
        assert key.startswith("intent:")

    @pytest.mark.asyncio
    async def test_invalidate_intent(self, cache_manager, mock_redis):
        await cache_manager.invalidate_intent("查询订单")
        mock_redis.delete.assert_called_once()
        key = mock_redis.delete.call_args[0][0]
        assert key.startswith("intent:")


class TestCacheManagerProfile:
    @pytest.mark.asyncio
    async def test_get_profile_cache_hit(self, cache_manager, mock_redis):
        profile = {"user_id": 1, "membership_level": "gold"}
        mock_redis.get = AsyncMock(return_value=json.dumps(profile))
        result = await cache_manager.get_profile(1)
        assert result == profile
        assert cache_manager._stats["profile"]["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_profile_cache_miss(self, cache_manager, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await cache_manager.get_profile(1)
        assert result is None
        assert cache_manager._stats["profile"]["misses"] == 1

    @pytest.mark.asyncio
    async def test_set_profile(self, cache_manager, mock_redis):
        profile = {"user_id": 1, "membership_level": "gold"}
        await cache_manager.set_profile(1, profile)
        mock_redis.setex.assert_called_once()
        assert mock_redis.setex.call_args[0][0] == "profile:1"

    @pytest.mark.asyncio
    async def test_invalidate_profile(self, cache_manager, mock_redis):
        await cache_manager.invalidate_profile(1)
        mock_redis.delete.assert_called_once_with("profile:1")

    @pytest.mark.asyncio
    async def test_invalidate_all_profiles(self, cache_manager, mock_redis):
        mock_redis.scan_iter = _make_async_iter(["profile:1", "profile:2"])
        await cache_manager.invalidate_all_profiles()
        mock_redis.delete.assert_called_once_with("profile:1", "profile:2")


class TestCacheManagerRetrieval:
    @pytest.mark.asyncio
    async def test_get_retrieval_cache_hit(self, cache_manager, mock_redis):
        chunks = [{"content": "policy A", "score": 0.95}]
        mock_redis.get = AsyncMock(return_value=json.dumps(chunks))
        result = await cache_manager.get_retrieval("退货政策")
        assert result == chunks
        assert cache_manager._stats["retrieval"]["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_retrieval_cache_miss(self, cache_manager, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await cache_manager.get_retrieval("退货政策")
        assert result is None
        assert cache_manager._stats["retrieval"]["misses"] == 1

    @pytest.mark.asyncio
    async def test_set_retrieval(self, cache_manager, mock_redis):
        chunks = [{"content": "policy A", "score": 0.95}]
        await cache_manager.set_retrieval("退货政策", chunks)
        mock_redis.setex.assert_called_once()
        key = mock_redis.setex.call_args[0][0]
        assert key.startswith("retrieval:")

    @pytest.mark.asyncio
    async def test_invalidate_all_retrieval(self, cache_manager, mock_redis):
        mock_redis.scan_iter = _make_async_iter(["retrieval:abc", "retrieval:def"])
        await cache_manager.invalidate_all_retrieval()
        mock_redis.delete.assert_called_once_with("retrieval:abc", "retrieval:def")


class TestCacheManagerBulkInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache_manager, mock_redis):
        async def _scan_iter(match):
            if match == "intent:*":
                yield "intent:a"
            elif match == "profile:*":
                yield "profile:b"
            elif match == "retrieval:*":
                yield "retrieval:c"

        mock_redis.scan_iter = _scan_iter
        mock_redis.delete = AsyncMock(return_value=3)
        await cache_manager.invalidate_all()
        assert mock_redis.delete.call_count == 3


class TestCacheManagerRedisErrorHandling:
    @pytest.mark.asyncio
    async def test_get_intent_redis_error_returns_none(self, cache_manager, mock_redis):
        mock_redis.get = AsyncMock(side_effect=aioredis.ConnectionError("timeout"))
        result = await cache_manager.get_intent("查询订单")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_intent_redis_error_silently_ignored(self, cache_manager, mock_redis):
        mock_redis.setex = AsyncMock(side_effect=aioredis.ConnectionError("timeout"))
        intent_data = {"primary_intent": "ORDER"}
        await cache_manager.set_intent("查询订单", intent_data)

    @pytest.mark.asyncio
    async def test_delete_pattern_redis_error_silently_ignored(self, cache_manager, mock_redis):
        async def _failing_scan(*args, **kwargs):
            yield "x"
            raise aioredis.ConnectionError("timeout")

        mock_redis.scan_iter = _failing_scan
        await cache_manager.invalidate_all_profiles()
