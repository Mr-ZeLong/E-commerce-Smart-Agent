"""Auto-healing tasks for the E-commerce Smart Agent.

Periodic Celery tasks that detect and remediate common operational issues
such as stuck workers and high Redis memory usage.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from app.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


from celery.app.control import Control


@celery_app.task(bind=True, name="autoheal.check_celery_workers")
def check_celery_workers(_self) -> dict:
    control = Control(celery_app)
    try:
        stats = control.inspect().stats()
        active = control.inspect().active()
    except Exception as exc:
        logger.warning("Failed to inspect Celery workers: %s", exc)
        return {"restarted_workers": 0, "error": str(exc)}

    restarted = 0
    if active and stats:
        for worker_name, tasks in active.items():
            worker_stats = stats.get(worker_name, {})
            uptime = worker_stats.get("uptime", 0)
            if tasks and uptime > 3600:
                logger.warning(
                    "Worker %s looks stuck (uptime %ds, %d active tasks)",
                    worker_name,
                    uptime,
                    len(tasks),
                )
                try:
                    control.broadcast("shutdown", destination=[worker_name])
                    restarted += 1
                except Exception as exc:
                    logger.exception("Failed to shutdown worker %s: %s", worker_name, exc)

    return {"restarted_workers": restarted}


import redis as sync_redis


@celery_app.task(bind=True, name="autoheal.clear_redis_cache")
def clear_redis_cache(_self, memory_threshold_mb: float = 512.0) -> dict:
    redis_url = settings.REDIS_URL
    try:
        client = sync_redis.from_url(redis_url, decode_responses=True)
    except Exception as exc:
        logger.warning("Failed to create Redis client: %s", exc)
        return {"error": str(exc)}

    try:
        info = cast(dict[str, Any], client.info("memory"))
        used_memory = info.get("used_memory", 0)
        used_mb = used_memory / (1024 * 1024)

        if used_mb < memory_threshold_mb:
            return {
                "memory_before_mb": used_mb,
                "memory_after_mb": used_mb,
                "keys_removed": 0,
                "threshold_mb": memory_threshold_mb,
            }

        logger.warning(
            "Redis memory %.1fMB > threshold %.1fMB; clearing cache", used_mb, memory_threshold_mb
        )

        patterns = ["cache:*", "rate_limit:*", "temp:*"]
        removed = 0
        for pattern in patterns:
            keys = []
            for key in client.scan_iter(match=pattern, count=1000):
                keys.append(key)
            if keys:
                client.delete(*keys)
                removed += len(keys)

        info_after: dict = client.info("memory")  # type: ignore[assignment]
        used_after_mb = info_after.get("used_memory", 0) / (1024 * 1024)

        return {
            "memory_before_mb": used_mb,
            "memory_after_mb": used_after_mb,
            "keys_removed": removed,
            "threshold_mb": memory_threshold_mb,
        }
    except Exception as exc:
        logger.exception("Redis cache clear failed")
        return {"error": str(exc)}
    finally:
        client.close()
