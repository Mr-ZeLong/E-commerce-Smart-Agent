from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.checkpointer import OptimizedRedisCheckpoint


class TestComputeDiff:
    def test_empty_diff(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1, "b": 2}
        diff = OptimizedRedisCheckpoint._compute_diff(old, new)
        assert diff == {}

    def test_added_key(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        diff = OptimizedRedisCheckpoint._compute_diff(old, new)
        assert diff == {"b": 2}

    def test_changed_key(self):
        old = {"a": 1}
        new = {"a": 2}
        diff = OptimizedRedisCheckpoint._compute_diff(old, new)
        assert diff == {"a": 2}

    def test_deleted_key(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        diff = OptimizedRedisCheckpoint._compute_diff(old, new)
        assert diff == {"b": {"__deleted__": True}}

    def test_nested_diff(self):
        old = {"a": {"x": 1, "y": 2}}
        new = {"a": {"x": 1, "y": 3}}
        diff = OptimizedRedisCheckpoint._compute_diff(old, new)
        assert diff == {"a": {"y": 3}}


class TestApplyDiff:
    def test_identity(self):
        base = {"a": 1, "b": 2}
        diff = {}
        result = OptimizedRedisCheckpoint._apply_diff(base, diff)
        assert result == {"a": 1, "b": 2}

    def test_add_and_change(self):
        base = {"a": 1}
        diff = {"b": 2, "a": 3}
        result = OptimizedRedisCheckpoint._apply_diff(base, diff)
        assert result == {"a": 3, "b": 2}

    def test_delete(self):
        base = {"a": 1, "b": 2}
        diff = {"b": {"__deleted__": True}}
        result = OptimizedRedisCheckpoint._apply_diff(base, diff)
        assert result == {"a": 1}

    def test_does_not_mutate_base(self):
        base = {"a": 1}
        diff = {"b": 2}
        OptimizedRedisCheckpoint._apply_diff(base, diff)
        assert base == {"a": 1}


@pytest.mark.asyncio
async def test_aput_stores_base_when_no_previous():
    redis_mock = AsyncMock()
    redis_mock.zcard.return_value = 0
    redis_mock.get.return_value = None

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()

    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}}
    checkpoint = {"id": "c1", "channel_values": {"x": 1}}

    result = await saver.aput(config, checkpoint, {}, {}, "values")

    assert result["configurable"]["checkpoint_id"] == "c1"
    redis_mock.setex.assert_called_once()
    call_args = redis_mock.setex.call_args[0]
    assert call_args[0].startswith("ckpt_opt:t1::c1")
    assert call_args[1] == 30 * 24 * 3600

    redis_mock.zadd.assert_called_once()
    redis_mock.expire.assert_called_once()


@pytest.mark.asyncio
async def test_aput_stores_diff_when_previous_exists():
    redis_mock = AsyncMock()
    redis_mock.zcard.return_value = 1
    redis_mock.get.side_effect = [
        None,
        None,
    ]

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()

    prev = {"id": "c0", "channel_values": {"x": 1}}
    curr = {"id": "c1", "channel_values": {"x": 2}}

    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}}

    with patch.object(saver, "aget", return_value=prev):
        result = await saver.aput(config, curr, {}, {}, "values")

    assert result["configurable"]["checkpoint_id"] == "c1"
    assert redis_mock.setex.call_count == 1
    assert redis_mock.zadd.call_count == 1


@pytest.mark.asyncio
async def test_aget_returns_base_checkpoint():
    import json
    import zlib

    redis_mock = AsyncMock()
    payload = {"__base__": True, "data": {"id": "c1", "channel_values": {"x": 1}}}
    compressed = zlib.compress(json.dumps(payload).encode())
    redis_mock.get.return_value = compressed

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()
    saver._base_saver.aget_tuple.return_value = None

    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "c1"}}
    result = await saver.aget(config)

    assert result == {"id": "c1", "channel_values": {"x": 1}}


@pytest.mark.asyncio
async def test_aget_reconstructs_from_diff():
    import json
    import zlib

    redis_mock = AsyncMock()

    base_payload = {"__base__": True, "data": {"id": "c0", "channel_values": {"x": 1}}}
    diff_payload = {
        "__base__": False,
        "parent_id": "c0",
        "diff": {"channel_values": {"x": 2}},
    }

    def mock_get(key):
        if b"c1" in key.encode():
            return zlib.compress(json.dumps(diff_payload).encode())
        if b"c0" in key.encode():
            return zlib.compress(json.dumps(base_payload).encode())
        return None

    redis_mock.get.side_effect = mock_get

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()
    saver._base_saver.aget_tuple.return_value = None

    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "c1"}}
    result = await saver.aget(config)

    assert result["channel_values"] == {"x": 2}


@pytest.mark.asyncio
async def test_aget_fallback_to_base_saver():
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    base_tuple = MagicMock()
    base_tuple.checkpoint = {"id": "c1"}

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()
    saver._base_saver.aget_tuple.return_value = base_tuple

    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "c1"}}
    result = await saver.aget(config)

    assert result == {"id": "c1"}
    saver._base_saver.aget_tuple.assert_called_once_with(config)


@pytest.mark.asyncio
async def test_aprune_calls_base_saver_and_cleans_optimized():
    redis_mock = AsyncMock()
    redis_mock.zrange.return_value = [b"c0", b"c1", b"c2"]

    async def _scan_iter(*args, **kwargs):
        yield "ckpt_index:t1:ns1"

    redis_mock.scan_iter = _scan_iter

    pipe_mock = AsyncMock()
    redis_mock.pipeline = MagicMock(return_value=pipe_mock)

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()

    await saver.aprune(["t1"], strategy="keep_latest")

    saver._base_saver.aprune.assert_called_once_with(["t1"], strategy="keep_latest")
    assert redis_mock.pipeline.call_count == 1


@pytest.mark.asyncio
async def test_aprune_keep_latest_retains_most_recent():
    redis_mock = AsyncMock()
    redis_mock.zrange.return_value = [b"c0", b"c1", b"c2"]

    async def _scan_iter(*args, **kwargs):
        yield "ckpt_index:t1:ns1"

    redis_mock.scan_iter = _scan_iter

    pipe_mock = AsyncMock()
    redis_mock.pipeline = MagicMock(return_value=pipe_mock)

    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()

    await saver.aprune(["t1"], strategy="keep_latest")

    assert pipe_mock.delete.call_count == 2
    pipe_mock.zrem.assert_called_once()


@pytest.mark.asyncio
async def test_setup_delegates_to_base_saver():
    redis_mock = AsyncMock()
    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()

    await saver.setup()
    saver._base_saver.setup.assert_awaited_once()


@pytest.mark.asyncio
async def test_aput_falls_back_when_missing_ids():
    redis_mock = AsyncMock()
    saver = OptimizedRedisCheckpoint(redis_client=redis_mock)
    saver._base_saver = AsyncMock()

    config = {"configurable": {"thread_id": "", "checkpoint_ns": ""}}
    checkpoint = {"id": ""}

    await saver.aput(config, checkpoint, {}, {}, "values")
    saver._base_saver.aput.assert_awaited_once()
