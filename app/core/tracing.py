"""Central LangSmith tracing utilities for LLM call metadata.

This module provides helpers to build RunnableConfig objects enriched with
LangSmith metadata and tags. Every LLM call in the project should pass a
config built via ``build_llm_config()`` so that LangSmith traces contain
useful context (agent name, user id, thread id, intent, etc.).

Usage::

    from app.core.tracing import build_llm_config

    config = build_llm_config(
        agent_name="order_agent",
        user_id=42,
        thread_id="thread-123",
        intent="ORDER",
        tags=["user_visible"],
        extra_metadata={"trace_id": "abc"},
    )
    response = await llm.ainvoke(messages, config=config)
"""

from __future__ import annotations

from typing import Any, cast

from langchain_core.runnables import RunnableConfig


def build_llm_config(
    *,
    agent_name: str | None = None,
    user_id: int | None = None,
    thread_id: str | None = None,
    intent: str | None = None,
    tags: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> RunnableConfig:
    """Build a RunnableConfig with LangSmith metadata and tags.

    Args:
        agent_name: Identifier for the agent / component making the LLM call.
        user_id: Current user id (for multi-tenant isolation visibility).
        thread_id: Conversation thread id.
        intent: Recognised intent category (e.g. ``"ORDER"``, ``"POLICY"``).
        tags: LangSmith tags for filtering / grouping (e.g.
            ``["user_visible"]``, ``["internal", "confidence_eval"]``).
        extra_metadata: Arbitrary additional metadata to attach to the run.

    Returns:
        A ``RunnableConfig`` dict containing ``metadata`` and optionally
        ``tags``. Pass this directly to ``llm.ainvoke(messages, config=config)``.
    """
    metadata: dict[str, Any] = {}
    if user_id is not None:
        metadata["user_id"] = user_id
    if thread_id is not None:
        metadata["thread_id"] = thread_id
    if agent_name is not None:
        metadata["agent_name"] = agent_name
    if intent is not None:
        metadata["intent"] = intent
    if extra_metadata:
        metadata.update(extra_metadata)

    config: RunnableConfig = cast(RunnableConfig, {"metadata": metadata})
    if tags:
        config = cast(RunnableConfig, {**config, "tags": tags})
    return config


def merge_configs(base: RunnableConfig | None, override: RunnableConfig | None) -> RunnableConfig:
    """Merge two RunnableConfigs, with *override* taking precedence.

    Both ``metadata`` and ``tags`` dicts are shallow-merged. All other keys
    are replaced by the override value.

    Args:
        base: The original config (e.g. from ``build_llm_config``).
        override: The config whose values should win.

    Returns:
        A new merged ``RunnableConfig``.
    """
    if base is None:
        return override or cast(RunnableConfig, {})
    if override is None:
        return base

    merged = dict(base)
    for key, value in override.items():
        if key in ("metadata", "tags") and key in merged and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return cast(RunnableConfig, merged)


def get_langsmith_run_url(callback) -> str | None:
    """Safely extract the public LangSmith run URL from a callback object.

    This helper is used after graph execution wrapped with
    ``tracing_v2_enabled()`` to persist the trace URL for observability.

    Args:
        callback: The callback returned by ``tracing_v2_enabled()`` context
            manager (may be ``None`` if tracing is disabled).

    Returns:
        The public LangSmith run URL, or ``None`` if unavailable.
    """
    if callback is None:
        return None
    try:
        return callback.get_run_url()
    except (AttributeError, TypeError):
        return None
