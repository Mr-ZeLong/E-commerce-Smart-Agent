"""Celery tasks for checkpoint maintenance."""

import logging
from typing import Any

from asgiref.sync import async_to_sync

from app.celery_app import celery_app
from app.core.redis import create_redis_client
from app.observability.metrics import record_checkpoint_cleanup

logger = logging.getLogger(__name__)

_MAX_CHECKPOINTS_PER_THREAD = 100


async def _cleanup_checkpoints_async() -> dict[str, Any]:
    redis_client = create_redis_client()
    try:
        total_removed = 0

        async for key in redis_client.scan_iter(match="ckpt_index:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            parts = key_str.split(":")
            if len(parts) < 3:
                continue
            thread_id = parts[1]
            checkpoint_ns = ":".join(parts[2:])

            ids = await redis_client.zrange(key_str, 0, -1)
            if len(ids) > _MAX_CHECKPOINTS_PER_THREAD:
                to_remove = ids[: len(ids) - _MAX_CHECKPOINTS_PER_THREAD]
                pipe = redis_client.pipeline()
                for cid in to_remove:
                    cid_str = cid.decode() if isinstance(cid, bytes) else cid
                    opt_key = f"ckpt_opt:{thread_id}:{checkpoint_ns}:{cid_str}"
                    pipe.delete(opt_key)
                pipe.zrem(key_str, *to_remove)
                await pipe.execute()
                total_removed += len(to_remove)
                record_checkpoint_cleanup(len(to_remove))

        return {"status": "success", "removed": total_removed}
    except Exception:
        logger.exception("Checkpoint cleanup failed")
        return {"status": "failed", "removed": 0}
    finally:
        await redis_client.aclose()


@celery_app.task(name="checkpoint.cleanup_old_checkpoints")
def cleanup_old_checkpoints() -> dict[str, Any]:
    return async_to_sync(_cleanup_checkpoints_async)()
