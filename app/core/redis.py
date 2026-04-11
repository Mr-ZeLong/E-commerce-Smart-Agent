import redis.asyncio as aioredis

from app.core.config import settings


def create_redis_client() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
