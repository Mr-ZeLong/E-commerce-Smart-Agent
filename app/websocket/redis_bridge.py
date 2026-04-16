"""Redis pub/sub bridge for WebSocket broadcasting across processes."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisBroadcastBridge:
    """Minimal Redis pub/sub bridge for cross-process WebSocket broadcasts."""

    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, event: str, data: dict[str, Any], room: str) -> None:
        """Publish a JSON payload to the Redis channel for the given room."""
        channel = f"ws:room:{room}"
        payload = json.dumps({"event": event, "data": data, "room": room})
        try:
            await self._redis.publish(channel, payload)
        except Exception:
            logger.exception("Failed to publish WebSocket message to Redis channel %s", channel)

    async def subscribe(self, room: str) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator that listens to the Redis channel for the given room."""
        channel = f"ws:room:{room}"
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(channel)
        except Exception:
            logger.exception("Failed to subscribe to Redis channel %s", channel)
            return

        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in Redis pubsub message on %s", channel)
                        continue
                    yield payload
        except Exception:
            logger.exception("Error in Redis pubsub listener for channel %s", channel)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                logger.exception("Error closing Redis pubsub for channel %s", channel)

    async def close(self) -> None:
        """Close the underlying Redis client."""
        try:
            await self._redis.aclose()
        except Exception:
            logger.exception("Error closing Redis client")
