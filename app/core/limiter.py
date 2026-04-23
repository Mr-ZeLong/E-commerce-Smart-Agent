# app/core/limiter.py
"""Rate limiter configuration using slowapi with Redis storage."""

import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status
from slowapi import Limiter

from app.core.config import settings


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=settings.REDIS_URL,
    in_memory_fallback_enabled=False,
    swallow_errors=False,
    headers_enabled=True,
)


async def check_user_rate_limit(
    redis: aioredis.Redis,
    user_id: int,
    max_requests: int = 10,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """Check per-user rate limit using fixed window algorithm.

    Args:
        redis: Async Redis client.
        user_id: Current user ID.
        max_requests: Maximum allowed requests per window.
        window_seconds: Time window in seconds.

    Returns:
        Tuple of (allowed: bool, remaining: int).

    Raises:
        HTTPException: 429 Too Many Requests if limit exceeded.
    """
    window_key = int(time.time()) // window_seconds
    key = f"rate_limit:user:{user_id}:{window_key}"

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    results = await pipe.execute()
    count = results[0]

    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试。",
            headers={"Retry-After": str(window_seconds - (int(time.time()) % window_seconds))},
        )

    remaining = max(0, max_requests - count)
    return True, remaining
