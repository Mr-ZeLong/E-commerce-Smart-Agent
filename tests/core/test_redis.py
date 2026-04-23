"""Tests for Redis connection pool, health check, and circuit breaker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as aioredis

from app.core.redis import (
    CircuitBreaker,
    CircuitState,
    RedisHealthCheck,
    _create_connection_pool,
    _get_circuit_breaker,
    _get_pool,
    create_redis_client,
    create_redis_client_with_circuit_breaker,
    create_redis_health_check,
)


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        mock_coro = AsyncMock(return_value="success")
        result = await breaker.call(mock_coro())
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        mock_coro = AsyncMock(side_effect=ConnectionError("boom"))

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(mock_coro())

        assert breaker.state == CircuitState.OPEN
        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            await breaker.call(mock_coro())

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        mock_coro = AsyncMock(side_effect=ConnectionError("boom"))

        with pytest.raises(ConnectionError):
            await breaker.call(mock_coro())

        assert breaker.state == CircuitState.OPEN
        await asyncio.sleep(0.02)

        success_coro = AsyncMock(return_value="ok")
        result = await breaker.call(success_coro())
        assert result == "ok"
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_half_open_successes(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=2)
        mock_coro = AsyncMock(side_effect=ConnectionError("boom"))

        with pytest.raises(ConnectionError):
            await breaker.call(mock_coro())

        await asyncio.sleep(0.02)

        success_coro = AsyncMock(return_value="ok")
        await breaker.call(success_coro())
        assert breaker.state == CircuitState.HALF_OPEN
        await breaker.call(success_coro())
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_returns_to_open(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=2)
        mock_coro = AsyncMock(side_effect=ConnectionError("boom"))

        with pytest.raises(ConnectionError):
            await breaker.call(mock_coro())

        await asyncio.sleep(0.02)

        fail_coro = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(RuntimeError):
            await breaker.call(fail_coro())

        assert breaker.state == CircuitState.OPEN


class TestRedisHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_when_ping_succeeds(self):
        mock_redis = MagicMock(spec=aioredis.Redis)
        mock_redis.ping = AsyncMock(return_value=True)
        checker = RedisHealthCheck(mock_redis)
        assert await checker.check() is True
        assert checker.is_healthy is True
        assert mock_redis.ping.call_count == 1

    @pytest.mark.asyncio
    async def test_unhealthy_after_max_retries(self):
        mock_redis = MagicMock(spec=aioredis.Redis)
        mock_redis.ping = AsyncMock(side_effect=aioredis.ConnectionError("timeout"))
        checker = RedisHealthCheck(mock_redis, max_retries=2, retry_delay=0.01)
        assert await checker.check() is False
        assert checker.is_healthy is False
        assert mock_redis.ping.call_count == 2

    @pytest.mark.asyncio
    async def test_recovers_after_failure(self):
        mock_redis = MagicMock(spec=aioredis.Redis)
        mock_redis.ping = AsyncMock(
            side_effect=[
                aioredis.ConnectionError("timeout"),
                True,
            ]
        )
        checker = RedisHealthCheck(mock_redis, max_retries=2, retry_delay=0.01)
        assert await checker.check() is True
        assert checker.is_healthy is True


class TestConnectionPool:
    def test_create_connection_pool_returns_pool(self):
        with patch("app.core.redis.AsyncConnectionPool.from_url") as mock_from_url:
            mock_pool = MagicMock()
            mock_from_url.return_value = mock_pool
            pool = _create_connection_pool()
            assert pool is mock_pool
            mock_from_url.assert_called_once()
            kwargs = mock_from_url.call_args.kwargs
            assert kwargs["max_connections"] == 50
            assert kwargs["decode_responses"] is True

    def test_get_pool_singleton(self):
        with patch("app.core.redis._create_connection_pool") as mock_create:
            mock_pool = MagicMock()
            mock_create.return_value = mock_pool
            p1 = _get_pool()
            p2 = _get_pool()
            assert p1 is p2
            mock_create.assert_called_once()

    def test_create_redis_client_uses_pool(self):
        with patch("app.core.redis._get_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_get_pool.return_value = mock_pool
            with patch("app.core.redis.aioredis.Redis") as mock_redis_cls:
                mock_client = MagicMock()
                mock_redis_cls.return_value = mock_client
                client = create_redis_client()
                assert client is mock_client
                mock_redis_cls.assert_called_once_with(connection_pool=mock_pool)


class TestCircuitBreakerFactory:
    def test_get_circuit_breaker_singleton(self):
        with patch("app.core.redis.CircuitBreaker") as mock_cls:
            mock_breaker = MagicMock()
            mock_cls.return_value = mock_breaker
            b1 = _get_circuit_breaker()
            b2 = _get_circuit_breaker()
            assert b1 is b2
            mock_cls.assert_called_once()

    def test_create_redis_client_with_circuit_breaker(self):
        with (
            patch("app.core.redis.create_redis_client") as mock_client,
            patch("app.core.redis._get_circuit_breaker") as mock_breaker,
        ):
            client, breaker = create_redis_client_with_circuit_breaker()
            assert client is mock_client.return_value
            assert breaker is mock_breaker.return_value


class TestRedisHealthCheckFactory:
    def test_create_health_check_with_provided_client(self):
        mock_redis = MagicMock(spec=aioredis.Redis)
        checker = create_redis_health_check(mock_redis)
        assert checker.redis is mock_redis

    def test_create_health_check_creates_new_client(self):
        with patch("app.core.redis.create_redis_client") as mock_create:
            mock_client = MagicMock(spec=aioredis.Redis)
            mock_create.return_value = mock_client
            checker = create_redis_health_check()
            assert checker.redis is mock_client
