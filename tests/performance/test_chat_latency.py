"""Performance regression tests for chat endpoint optimizations.

Validates that async PII filtering, Redis client reuse, and background
post-streaming DB writes reduce perceived latency.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.chat import _log_post_chat_metrics, _safe_vector_upsert


class TestBackgroundTaskLatency:
    """Verify fire-and-forget patterns do not block the caller."""

    @pytest.mark.asyncio
    async def test_safe_vector_upsert_is_non_blocking(self):
        """_safe_vector_upsert should return immediately and complete in background."""
        mock_vm = AsyncMock()
        mock_vm.upsert_message = AsyncMock(side_effect=lambda **kwargs: asyncio.sleep(0.2))

        t0 = time.perf_counter()
        task = asyncio.create_task(
            _safe_vector_upsert(
                vector_manager=mock_vm,
                user_id=1,
                thread_id="t1",
                message_role="user",
                content="hello",
                timestamp="2024-01-01T00:00:00",
            )
        )
        # Yield to let the task start, but do not await it.
        await asyncio.sleep(0)
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.05, f"Caller should not be blocked by upsert ({elapsed:.3f}s)"
        # Ensure the background task eventually completes.
        await asyncio.wait_for(task, timeout=1.0)
        mock_vm.upsert_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_post_chat_metrics_is_non_blocking_pattern(self):
        """_log_post_chat_metrics should be callable via create_task without blocking."""
        with patch("app.api.v1.chat.async_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

            t0 = time.perf_counter()
            task = asyncio.create_task(
                _log_post_chat_metrics(
                    thread_id="t1",
                    user_id=1,
                    final_state={"current_agent": "test_agent"},
                    node_latencies={},
                    variant_id=None,
                    total_latency_ms=100,
                    langsmith_run_url=None,
                    intent_category="ORDER",
                    query_text="test",
                    variant_llm_model=None,
                )
            )
            await asyncio.sleep(0)
            elapsed = time.perf_counter() - t0

            assert elapsed < 0.05, f"Metrics logging should not block caller ({elapsed:.3f}s)"
            await asyncio.wait_for(task, timeout=1.0)


class TestAsyncPIIFilter:
    """Verify that the PII filter module exposes an async interface."""

    @pytest.mark.asyncio
    async def test_pii_filter_has_async_method(self):
        """pii_filter.afilter_text should exist and be awaitable."""
        from app.context.pii_filter import pii_filter

        assert hasattr(pii_filter, "afilter_text"), (
            "PIIFilter must expose an async afilter_text method"
        )
        result = await pii_filter.afilter_text("hello world")
        assert hasattr(result, "redacted_text")


class TestChatEndpointOptimizations:
    """High-level checks for chat.py optimization patterns."""

    def test_chat_uses_async_pii_filter(self):
        """chat() should await pii_filter.afilter_text, not the sync version."""
        import ast
        import inspect

        from app.api.v1 import chat as chat_module

        source = inspect.getsource(chat_module.chat)
        tree = ast.parse(source)

        # Walk the AST to find calls to afilter_text.
        found_async_filter = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute) and child.attr == "afilter_text":
                        found_async_filter = True
                        break

        assert found_async_filter, "chat endpoint should use await pii_filter.afilter_text()"

    def test_chat_reuses_shared_redis_client(self):
        """chat() should read redis_client from request.app.state."""
        import inspect

        from app.api.v1 import chat as chat_module

        source = inspect.getsource(chat_module.chat)
        assert (
            "request.app.state.redis_client" in source or "getattr(request.app.state" in source
        ), "chat endpoint should reuse the shared Redis client from app state"
