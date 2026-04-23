"""Rate limiter unit tests."""

import pytest
from fastapi import HTTPException

from app.core.limiter import check_user_rate_limit
from app.core.redis import create_redis_client


@pytest.mark.asyncio
async def test_check_user_rate_limit_allows_requests_within_limit():
    """check_user_rate_limit should allow requests within the limit."""
    redis = create_redis_client()
    try:
        user_id = 99901
        max_requests = 3

        # All requests within limit should succeed
        for _ in range(max_requests):
            allowed, remaining = await check_user_rate_limit(
                redis, user_id, max_requests=max_requests, window_seconds=60
            )
            assert allowed is True
            assert remaining >= 0
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_check_user_rate_limit_blocks_excess_requests():
    """check_user_rate_limit should raise 429 when limit is exceeded."""
    redis = create_redis_client()
    try:
        user_id = 99902
        max_requests = 2

        # Exhaust the limit
        for _ in range(max_requests):
            await check_user_rate_limit(
                redis, user_id, max_requests=max_requests, window_seconds=60
            )

        # Next request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await check_user_rate_limit(
                redis, user_id, max_requests=max_requests, window_seconds=60
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers is not None
        assert "Retry-After" in exc_info.value.headers
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_check_user_rate_limit_is_per_user():
    """Rate limits for different users should be independent."""
    redis = create_redis_client()
    try:
        max_requests = 2

        # Exhaust limit for user A
        for _ in range(max_requests):
            await check_user_rate_limit(redis, 99903, max_requests=max_requests, window_seconds=60)

        with pytest.raises(HTTPException) as exc_info:
            await check_user_rate_limit(redis, 99903, max_requests=max_requests, window_seconds=60)
        assert exc_info.value.status_code == 429

        # User B should still be allowed
        allowed, _ = await check_user_rate_limit(
            redis, 99904, max_requests=max_requests, window_seconds=60
        )
        assert allowed is True
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_check_user_rate_limit_remaining_decreases():
    """Remaining count should decrease with each request."""
    redis = create_redis_client()
    try:
        user_id = 99905
        max_requests = 5

        _, remaining = await check_user_rate_limit(
            redis, user_id, max_requests=max_requests, window_seconds=60
        )
        assert remaining == 4

        _, remaining = await check_user_rate_limit(
            redis, user_id, max_requests=max_requests, window_seconds=60
        )
        assert remaining == 3
    finally:
        await redis.aclose()
