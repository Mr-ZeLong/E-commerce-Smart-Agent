"""Prometheus metrics for the E-commerce Smart Agent.

Provides custom application metrics alongside the existing OpenTelemetry tracing.
All metric recording functions are async-safe and non-blocking.
"""

from __future__ import annotations

from typing import cast

from prometheus_client import (  # type: ignore[import-not-found] - prometheus-client is installed but lacks stubs
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


def _get_or_create_gauge(name: str, description: str, labels: list[str] | None = None) -> Gauge:
    """Return an existing Gauge or create a new one."""
    try:
        return Gauge(name, description, labels or [])
    except ValueError:
        return cast(Gauge, REGISTRY._names_to_collectors[name])


def _get_or_create_counter(name: str, description: str, labels: list[str] | None = None) -> Counter:
    """Return an existing Counter or create a new one."""
    try:
        return Counter(name, description, labels or [])
    except ValueError:
        return cast(Counter, REGISTRY._names_to_collectors[name])


def _get_or_create_histogram(
    name: str, description: str, labels: list[str] | None = None, buckets: tuple | None = None
) -> Histogram:
    """Return an existing Histogram or create a new one."""
    try:
        kwargs: dict = {}
        if buckets is not None:
            kwargs["buckets"] = buckets
        return Histogram(name, description, labels or [], **kwargs)
    except ValueError:
        return cast(Histogram, REGISTRY._names_to_collectors[name])


CHAT_REQUESTS_TOTAL = _get_or_create_counter(
    "chat_requests_total",
    "Total number of chat requests received.",
    ["intent_category", "final_agent"],
)

CHAT_ERRORS_TOTAL = _get_or_create_counter(
    "chat_errors_total",
    "Total number of chat request errors.",
    ["error_type"],
)

CHAT_LATENCY_SECONDS = _get_or_create_histogram(
    "chat_latency_seconds",
    "End-to-end chat request latency in seconds.",
    ["final_agent"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

NODE_LATENCY_SECONDS = _get_or_create_histogram(
    "node_latency_seconds",
    "Individual graph node execution latency in seconds.",
    ["node_name"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TOKEN_USAGE_TOTAL = _get_or_create_counter(
    "token_usage_total",
    "Total number of tokens consumed by LLM calls.",
    ["agent"],
)

CONTEXT_UTILIZATION_RATIO = _get_or_create_gauge(
    "context_utilization_ratio",
    "Ratio of context tokens used vs budget (0.0-1.0).",
)

HUMAN_TRANSFERS_TOTAL = _get_or_create_counter(
    "human_transfers_total",
    "Total number of requests transferred to human agents.",
    ["reason"],
)

INTENT_ACCURACY = _get_or_create_gauge(
    "intent_accuracy",
    "Accuracy of intent classification (0.0-1.0).",
    ["intent_category"],
)

RAG_PRECISION = _get_or_create_gauge(
    "rag_precision",
    "Precision of RAG retrieval (0.0-1.0).",
)

HALLUCINATION_RATE = _get_or_create_gauge(
    "hallucination_rate",
    "Rate of hallucinated responses (0.0-1.0).",
)

CONFIDENCE_SCORE = _get_or_create_histogram(
    "confidence_score",
    "Distribution of confidence scores.",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

AGENT_CONTEXT_TOKENS = _get_or_create_gauge(
    "agent_context_tokens",
    "Context tokens per agent after state filtering.",
    ["agent_name"],
)

AGENT_CONTEXT_REDUCTION_RATIO = _get_or_create_gauge(
    "agent_context_reduction_ratio",
    "Ratio of tokens saved by context isolation (0.0-1.0).",
    ["agent_name"],
)

REDIS_CONNECTIONS_ACTIVE = _get_or_create_gauge(
    "redis_connections_active",
    "Number of active Redis connections in the pool.",
)

REDIS_CONNECTION_ERRORS_TOTAL = _get_or_create_counter(
    "redis_connection_errors_total",
    "Total number of Redis connection errors.",
    ["error_type"],
)

REDIS_OPERATION_LATENCY_SECONDS = _get_or_create_histogram(
    "redis_operation_latency_seconds",
    "Latency of Redis operations in seconds.",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

REDIS_CACHE_HIT_RATIO = _get_or_create_gauge(
    "redis_cache_hit_ratio",
    "Cache hit ratio for Redis-backed caches (0.0-1.0).",
    ["cache_name"],
)

CHECKPOINT_SIZE_BYTES = _get_or_create_histogram(
    "checkpoint_size_bytes",
    "Compressed checkpoint size in bytes.",
    ["storage_type"],
    buckets=(128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288),
)

CHECKPOINT_COMPRESSION_RATIO = _get_or_create_histogram(
    "checkpoint_compression_ratio",
    "Compression ratio (uncompressed / compressed).",
    buckets=(1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0),
)

CHECKPOINT_CLEANUP_TOTAL = _get_or_create_counter(
    "checkpoint_cleanup_total",
    "Total number of old checkpoints removed by cleanup tasks.",
)


def record_checkpoint_metrics(compressed_size: int, uncompressed_size: int, is_base: bool) -> None:
    """Record checkpoint storage metrics."""
    storage_type = "base" if is_base else "diff"
    CHECKPOINT_SIZE_BYTES.labels(storage_type=storage_type).observe(compressed_size)
    if compressed_size > 0:
        CHECKPOINT_COMPRESSION_RATIO.observe(uncompressed_size / compressed_size)


def record_checkpoint_cleanup(count: int) -> None:
    """Record the number of checkpoints removed during cleanup."""
    CHECKPOINT_CLEANUP_TOTAL.inc(count)


def record_chat_request(
    intent_category: str | None = None,
    final_agent: str | None = None,
) -> None:
    """Increment the chat request counter."""
    CHAT_REQUESTS_TOTAL.labels(
        intent_category=intent_category or "unknown",
        final_agent=final_agent or "unknown",
    ).inc()


def record_chat_error(error_type: str) -> None:
    """Increment the chat error counter."""
    CHAT_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_chat_latency(latency_seconds: float, final_agent: str | None = None) -> None:
    """Observe chat end-to-end latency."""
    CHAT_LATENCY_SECONDS.labels(final_agent=final_agent or "unknown").observe(latency_seconds)


def record_node_latency(node_name: str, latency_seconds: float) -> None:
    """Observe individual node execution latency."""
    NODE_LATENCY_SECONDS.labels(node_name=node_name).observe(latency_seconds)


def record_token_usage(tokens: int, agent: str | None = None) -> None:
    """Record token consumption."""
    TOKEN_USAGE_TOTAL.labels(agent=agent or "unknown").inc(tokens)


def record_context_utilization(ratio: float) -> None:
    """Set the current context utilization ratio."""
    CONTEXT_UTILIZATION_RATIO.set(ratio)


def record_human_transfer(reason: str | None = None) -> None:
    """Increment the human transfer counter."""
    HUMAN_TRANSFERS_TOTAL.labels(reason=reason or "unknown").inc()


def record_confidence_score(score: float) -> None:
    """Observe a confidence score value."""
    CONFIDENCE_SCORE.observe(score)


def set_intent_accuracy(value: float, intent_category: str | None = None) -> None:
    """Set the intent classification accuracy gauge."""
    INTENT_ACCURACY.labels(intent_category=intent_category or "overall").set(value)


def set_rag_precision(value: float) -> None:
    """Set the RAG precision gauge."""
    RAG_PRECISION.set(value)


def set_hallucination_rate(value: float) -> None:
    """Set the hallucination rate gauge."""
    HALLUCINATION_RATE.set(value)


def record_agent_context_tokens(tokens: int, agent_name: str | None = None) -> None:
    """Record per-agent context token count after filtering."""
    AGENT_CONTEXT_TOKENS.labels(agent_name=agent_name or "unknown").set(tokens)


def record_agent_context_reduction(agent_name: str, ratio: float) -> None:
    """Record the token reduction ratio achieved by context isolation."""
    AGENT_CONTEXT_REDUCTION_RATIO.labels(agent_name=agent_name).set(ratio)


def record_redis_connection_error(error_type: str) -> None:
    """Increment the Redis connection error counter."""
    REDIS_CONNECTION_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_redis_operation_latency(operation: str, latency_seconds: float) -> None:
    """Observe Redis operation latency."""
    REDIS_OPERATION_LATENCY_SECONDS.labels(operation=operation).observe(latency_seconds)


def set_redis_connections_active(count: int) -> None:
    """Set the number of active Redis connections."""
    REDIS_CONNECTIONS_ACTIVE.set(count)


def set_cache_hit_ratio(cache_name: str, ratio: float) -> None:
    """Set the cache hit ratio for a named cache."""
    REDIS_CACHE_HIT_RATIO.labels(cache_name=cache_name).set(ratio)


def get_metrics_response() -> tuple[bytes, str]:
    """Generate the latest Prometheus metrics payload."""
    return generate_latest(), CONTENT_TYPE_LATEST
