"""Redis client with connection pool, health check, and circuit breaker."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple async circuit breaker for Redis operations.

    After *failure_threshold* consecutive failures the circuit opens for
    *recovery_timeout* seconds.  In ``HALF_OPEN`` state up to
    *half_open_max_calls* successful calls are required before the circuit
    closes again.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, coro: Any) -> Any:
        """Execute *coro* if the circuit allows it.

        Raises:
            RuntimeError: When the circuit is OPEN.
        """
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker transitioned: OPEN -> HALF_OPEN")
                else:
                    raise RuntimeError("Circuit breaker is OPEN")

        try:
            result = await coro
            await self._record_success()
            return result
        except Exception as exc:
            await self._record_failure()
            raise exc

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        elapsed = asyncio.get_event_loop().time() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        "Circuit breaker transitioned: HALF_OPEN -> CLOSED "
                        "(%s consecutive successes)",
                        self.half_open_max_calls,
                    )
            else:
                self._failure_count = 0

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = asyncio.get_event_loop().time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker transitioned: HALF_OPEN -> OPEN (failure in half-open state)"
                )
            elif self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker transitioned: CLOSED -> OPEN (%s consecutive failures)",
                        self.failure_threshold,
                    )


class RedisHealthCheck:
    """Redis health checker with retry logic."""

    def __init__(
        self,
        redis: aioredis.Redis,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.redis = redis
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._healthy = True

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    async def check(self) -> bool:
        """Ping Redis with retries.

        Returns:
            True if Redis responds to PING, False otherwise.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                pong = await self.redis.ping()  # type: ignore
                if pong:
                    self._healthy = True
                    return True
            except aioredis.RedisError as exc:
                logger.warning(
                    "Redis health check attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)

        self._healthy = False
        return False


_pool_instance: AsyncConnectionPool | None = None
_breaker_instance: CircuitBreaker | None = None


def _create_connection_pool() -> AsyncConnectionPool:
    """Create a configured async Redis connection pool."""
    return AsyncConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
        retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
        socket_keepalive=settings.REDIS_SOCKET_KEEPALIVE,
        decode_responses=True,
    )


def _get_pool() -> AsyncConnectionPool:
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = _create_connection_pool()
    return _pool_instance


def _get_circuit_breaker() -> CircuitBreaker:
    global _breaker_instance
    if _breaker_instance is None:
        _breaker_instance = CircuitBreaker(
            failure_threshold=settings.REDIS_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=settings.REDIS_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            half_open_max_calls=settings.REDIS_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
        )
    return _breaker_instance


async def get_redis_client() -> aioredis.Redis:
    """Get the shared async Redis client (async-compatible wrapper).

    This is a convenience alias for :func:`create_redis_client` that
    returns the same pool-backed client.  Callers that need to ``await``
    the getter for API compatibility can use this function.
    """
    return create_redis_client()


def create_redis_client() -> aioredis.Redis:
    """Create an async Redis client using the shared connection pool.

    The returned client should be closed with ``await client.aclose()`` when
    it is no longer needed, or reused as a long-lived dependency.
    """
    pool = _get_pool()
    return aioredis.Redis(connection_pool=pool)


def create_redis_client_with_circuit_breaker() -> tuple[aioredis.Redis, CircuitBreaker]:
    """Create a Redis client together with the shared circuit breaker.

    Returns:
        A tuple of (redis_client, circuit_breaker).
    """
    return create_redis_client(), _get_circuit_breaker()


def create_redis_health_check(redis: aioredis.Redis | None = None) -> RedisHealthCheck:
    """Create a health checker for the given or a new Redis client."""
    client = redis or create_redis_client()
    return RedisHealthCheck(client)
