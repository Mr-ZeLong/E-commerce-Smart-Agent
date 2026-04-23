"""Optimized Redis checkpointer with diff-based storage and compression."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
import zlib
from typing import Any, cast

from langgraph.checkpoint.base import Checkpoint, CheckpointTuple
from langgraph.checkpoint.redis import AsyncRedisSaver

from app.observability.metrics import record_checkpoint_cleanup, record_checkpoint_metrics

logger = logging.getLogger(__name__)

_DEFAULT_TTL_DAYS = 30
_DEFAULT_BASE_EVERY = 10
_DEFAULT_COMPRESSION_LEVEL = 6


class OptimizedRedisCheckpoint:
    def __init__(
        self,
        redis_client: Any,
        ttl_days: int = _DEFAULT_TTL_DAYS,
        base_every: int = _DEFAULT_BASE_EVERY,
        compression_level: int = _DEFAULT_COMPRESSION_LEVEL,
    ) -> None:
        self._redis = redis_client
        self._base_saver = AsyncRedisSaver(redis_client=redis_client)
        self._ttl_seconds = ttl_days * 24 * 3600
        self._base_every = max(1, base_every)
        self._compression_level = compression_level

    async def setup(self) -> None:
        await self._base_saver.setup()

    async def aput(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
        stream_mode: str = "values",
    ) -> Any:
        configurable = (config.get("configurable") or {}).copy()
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = checkpoint.get("id", "")

        if not thread_id or not checkpoint_id:
            logger.warning("Missing thread_id or checkpoint_id, falling back to base saver")
            return await self._base_saver.aput(
                config, checkpoint, metadata, new_versions, stream_mode
            )

        prev_checkpoint = await self.aget(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}}
        )

        index_key = self._index_key(thread_id, checkpoint_ns)
        index_count = await self._redis.zcard(index_key)
        is_base = prev_checkpoint is None or (index_count % self._base_every == 0)

        if is_base:
            payload: dict[str, Any] = {"__base__": True, "data": checkpoint}
        else:
            diff = self._compute_diff(prev_checkpoint, checkpoint)
            payload = {
                "__base__": False,
                "parent_id": prev_checkpoint.get("id", ""),
                "diff": diff,
            }

        raw_bytes = json.dumps(payload, default=str).encode("utf-8")
        compressed = zlib.compress(raw_bytes, level=self._compression_level)

        opt_key = self._opt_key(thread_id, checkpoint_ns, checkpoint_id)
        await self._redis.setex(opt_key, self._ttl_seconds, compressed)

        await self._redis.zadd(index_key, {checkpoint_id: time.time()})
        await self._redis.expire(index_key, self._ttl_seconds)

        record_checkpoint_metrics(
            compressed_size=len(compressed),
            uncompressed_size=len(raw_bytes),
            is_base=is_base,
        )

        asyncio.create_task(
            self._safe_base_aput(config, checkpoint, metadata, new_versions, stream_mode)
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aget(self, config: Any) -> Any:
        tup = await self.aget_tuple(config)
        return tup.checkpoint if tup is not None else None

    async def aget_tuple(self, config: Any) -> CheckpointTuple | None:
        configurable = config.get("configurable") or {}
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = configurable.get("checkpoint_id")

        if not thread_id:
            return None

        opt_key = self._opt_key(thread_id, checkpoint_ns, checkpoint_id or "")
        compressed = await self._redis.get(opt_key)

        if compressed is not None:
            checkpoint = await self._reconstruct_from_opt(
                thread_id, checkpoint_ns, checkpoint_id, compressed
            )
            if checkpoint is not None:
                return CheckpointTuple(
                    config=config,
                    checkpoint=cast(Checkpoint, checkpoint),
                    metadata={},
                    parent_config=None,
                    pending_writes=None,
                )

        if not checkpoint_id:
            latest_key = f"checkpoint_latest_opt:{thread_id}:{checkpoint_ns}"
            latest_id = await self._redis.get(latest_key)
            if latest_id:
                opt_key = self._opt_key(thread_id, checkpoint_ns, latest_id)
                compressed = await self._redis.get(opt_key)
                if compressed is not None:
                    checkpoint = await self._reconstruct_from_opt(
                        thread_id, checkpoint_ns, latest_id, compressed
                    )
                    if checkpoint is not None:
                        return CheckpointTuple(
                            config=config,
                            checkpoint=cast(Checkpoint, checkpoint),
                            metadata={},
                            parent_config=None,
                            pending_writes=None,
                        )

        return await self._base_saver.aget_tuple(config)

    async def alist(
        self,
        config: Any | None = None,
        *,
        filter: Any | None = None,  # noqa: A002
        before: Any | None = None,
        limit: int | None = None,
    ) -> Any:
        return self._base_saver.alist(config, filter=filter, before=before, limit=limit)

    async def aprune(self, thread_ids: list[str], *, strategy: str = "keep_latest") -> None:
        await self._base_saver.aprune(thread_ids, strategy=strategy)

        for thread_id in thread_ids:
            async for key in self._redis.scan_iter(match=f"ckpt_index:{thread_id}:*"):
                key_str = key.decode() if isinstance(key, bytes) else key
                ns = key_str.split(":", 2)[2]
                await self._prune_optimized(thread_id, ns, strategy)

    @staticmethod
    def _compute_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for key, new_val in new.items():
            if key not in old:
                diff[key] = new_val
            elif old[key] != new_val:
                if isinstance(new_val, dict) and isinstance(old[key], dict):
                    nested = OptimizedRedisCheckpoint._compute_diff(old[key], new_val)
                    if nested:
                        diff[key] = nested
                else:
                    diff[key] = new_val
        for key in old:
            if key not in new:
                diff[key] = {"__deleted__": True}
        return diff

    @staticmethod
    def _apply_diff(base: dict[str, Any], diff: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(base)
        for key, val in diff.items():
            if isinstance(val, dict) and val.get("__deleted__") is True:
                result.pop(key, None)
            else:
                result[key] = val
        return result

    async def _reconstruct_from_opt(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str | None,
        compressed: bytes,
    ) -> dict[str, Any] | None:
        try:
            raw = zlib.decompress(compressed)
            payload = json.loads(raw.decode("utf-8"))
        except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Failed to decode optimised checkpoint: %s", exc)
            return None

        if payload.get("__base__"):
            return payload["data"]

        parent_id = payload.get("parent_id", "")
        diff_chain: list[dict[str, Any]] = [payload["diff"]]
        visited: set[str] = {checkpoint_id or ""}

        while parent_id:
            if parent_id in visited:
                logger.warning("Cycle detected in checkpoint diff chain")
                return None
            visited.add(parent_id)

            parent_key = self._opt_key(thread_id, checkpoint_ns, parent_id)
            parent_compressed = await self._redis.get(parent_key)
            if parent_compressed is None:
                logger.warning("Missing parent checkpoint %s for thread %s", parent_id, thread_id)
                return None

            try:
                parent_raw = zlib.decompress(parent_compressed)
                parent_payload = json.loads(parent_raw.decode("utf-8"))
            except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.warning("Failed to decode parent checkpoint: %s", exc)
                return None

            if parent_payload.get("__base__"):
                base_checkpoint = parent_payload["data"]
                for d in reversed(diff_chain):
                    base_checkpoint = self._apply_diff(base_checkpoint, d)
                return base_checkpoint

            parent_id = parent_payload.get("parent_id", "")
            diff_chain.append(parent_payload["diff"])

        logger.warning("Could not find base checkpoint for %s", checkpoint_id)
        return None

    async def _prune_optimized(self, thread_id: str, checkpoint_ns: str, strategy: str) -> None:
        index_key = self._index_key(thread_id, checkpoint_ns)
        if strategy == "keep_latest":
            ids = await self._redis.zrange(index_key, 0, -1)
            if len(ids) > 1:
                to_remove = ids[:-1]
                pipe = self._redis.pipeline()
                for cid in to_remove:
                    cid_str = cid.decode() if isinstance(cid, bytes) else cid
                    pipe.delete(self._opt_key(thread_id, checkpoint_ns, cid_str))
                pipe.zrem(index_key, *to_remove)
                await pipe.execute()
                record_checkpoint_cleanup(len(to_remove))
        else:
            ids = await self._redis.zrange(index_key, 0, -1)
            if ids:
                pipe = self._redis.pipeline()
                for cid in ids:
                    cid_str = cid.decode() if isinstance(cid, bytes) else cid
                    pipe.delete(self._opt_key(thread_id, checkpoint_ns, cid_str))
                pipe.delete(index_key)
                await pipe.execute()
                record_checkpoint_cleanup(len(ids))

    @staticmethod
    def _opt_key(thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"ckpt_opt:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    @staticmethod
    def _index_key(thread_id: str, checkpoint_ns: str) -> str:
        return f"ckpt_index:{thread_id}:{checkpoint_ns}"

    async def _safe_base_aput(
        self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any, stream_mode: str
    ) -> None:
        try:
            await self._base_saver.aput(config, checkpoint, metadata, new_versions, stream_mode)
        except Exception:
            logger.exception("Base saver aput failed (non-critical)")
