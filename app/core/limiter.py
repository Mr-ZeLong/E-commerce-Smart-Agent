# app/core/limiter.py
"""Rate limiter configuration using slowapi with Redis storage."""

from fastapi import Request
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
    in_memory_fallback_enabled=True,
    swallow_errors=True,
    headers_enabled=True,
)
