"""Auto-healing Celery tasks for operational remediation.

Extends the existing autoheal module with additional self-healing capabilities:
- Detect and restart stuck Celery workers
- Clear Redis cache when memory exceeds threshold
- Monitor and remediate database connection pool saturation
"""

from __future__ import annotations

import logging
from typing import Any, cast

from app.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="autoheal.restart_stuck_workers")
def restart_stuck_workers(_self, uptime_threshold_seconds: float = 3600.0) -> dict[str, Any]:
    """Detect and restart Celery workers that appear stuck.

    A worker is considered stuck if it has active tasks and has been running
    longer than the uptime threshold.
    """
    from celery.app.control import Control

    control = Control(celery_app)
    try:
        stats = control.inspect().stats()
        active = control.inspect().active()
    except Exception as exc:
        logger.warning("Failed to inspect Celery workers: %s", exc)
        return {"restarted": 0, "error": str(exc)}

    restarted = 0
    if active and stats:
        for worker_name, tasks in active.items():
            worker_stats = stats.get(worker_name, {})
            uptime = worker_stats.get("uptime", 0)
            if tasks and uptime > uptime_threshold_seconds:
                logger.warning(
                    "Worker %s appears stuck (uptime %ds, %d active tasks). Restarting...",
                    worker_name,
                    uptime,
                    len(tasks),
                )
                try:
                    control.broadcast("shutdown", destination=[worker_name])
                    restarted += 1
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to shutdown worker %s: %s", worker_name, exc)

    return {"restarted": restarted, "threshold_seconds": uptime_threshold_seconds}


@celery_app.task(bind=True, name="autoheal.clear_expired_redis_keys")
def clear_expired_redis_keys(_self, memory_threshold_mb: float = 512.0) -> dict[str, Any]:
    """Clear temporary Redis keys when memory usage exceeds threshold."""
    import redis as sync_redis

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
                "memory_mb": used_mb,
                "threshold_mb": memory_threshold_mb,
                "keys_removed": 0,
                "action": "skipped",
            }

        logger.warning(
            "Redis memory %.1fMB > threshold %.1fMB; clearing cache keys", used_mb, memory_threshold_mb
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

        info_after = cast(dict[str, Any], client.info("memory"))
        used_after_mb = info_after.get("used_memory", 0) / (1024 * 1024)

        return {
            "memory_before_mb": used_mb,
            "memory_after_mb": used_after_mb,
            "keys_removed": removed,
            "threshold_mb": memory_threshold_mb,
            "action": "cleared",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Redis cache clear failed")
        return {"error": str(exc)}
    finally:
        client.close()


@celery_app.task(bind=True, name="autoheal.check_db_pool_health")
def check_db_pool_health(_self, max_overflow_threshold: int = 20) -> dict[str, Any]:
    """Check database connection pool health and log warnings if saturated."""
    from sqlalchemy import text

    from app.core.database import sync_engine

    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
            active_connections = result.scalar() or 0

        pool_size = settings.DB_POOL_SIZE
        max_overflow = settings.DB_MAX_OVERFLOW
        total_capacity = pool_size + max_overflow
        utilization = active_connections / total_capacity if total_capacity > 0 else 0

        if active_connections > total_capacity - max_overflow_threshold:
            logger.warning(
                "Database connection pool near saturation: %d/%d connections (%.1f%%)",
                active_connections,
                total_capacity,
                utilization * 100,
            )
            return {
                "healthy": False,
                "active_connections": active_connections,
                "total_capacity": total_capacity,
                "utilization": round(utilization, 4),
                "action": "warning_logged",
            }

        return {
            "healthy": True,
            "active_connections": active_connections,
            "total_capacity": total_capacity,
            "utilization": round(utilization, 4),
            "action": "none",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Database pool health check failed")
        return {"healthy": False, "error": str(exc)}
