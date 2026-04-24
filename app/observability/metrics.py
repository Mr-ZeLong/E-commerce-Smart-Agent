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

ANSWER_CORRECTNESS = _get_or_create_gauge(
    "answer_correctness",
    "Answer correctness score from evaluator (0.0-1.0).",
    ["agent_type"],
)

AGENT_LATENCY_SECONDS = _get_or_create_histogram(
    "agent_latency_seconds",
    "Agent execution latency in seconds.",
    ["agent_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TOKEN_EFFICIENCY = _get_or_create_gauge(
    "token_efficiency",
    "Ratio of useful tokens to total tokens (0.0-1.0).",
    ["agent"],
)

TOKENS_TOTAL = _get_or_create_counter(
    "tokens_total",
    "Total tokens consumed across all agents.",
)

CACHE_HITS_TOTAL = _get_or_create_counter(
    "cache_hits_total",
    "Total cache hits.",
    ["cache_name"],
)

CACHE_MISSES_TOTAL = _get_or_create_counter(
    "cache_misses_total",
    "Total cache misses.",
    ["cache_name"],
)

HIGH_COST_REQUESTS_TOTAL = _get_or_create_counter(
    "high_cost_requests_total",
    "Total requests exceeding cost threshold.",
    ["agent"],
)

SAFETY_BLOCKS_TOTAL = _get_or_create_counter(
    "safety_blocks_total",
    "Total content moderation blocks.",
    ["layer", "reason"],
)

PII_DETECTIONS_TOTAL = _get_or_create_counter(
    "pii_detections_total",
    "Total PII detections by type.",
    ["pii_type", "source"],
)

INJECTION_ATTEMPTS_TOTAL = _get_or_create_counter(
    "injection_attempts_total",
    "Total prompt injection attempts detected.",
)

PII_BREACHES_TOTAL = _get_or_create_counter(
    "pii_breaches_total",
    "Total PII breaches (detections that bypassed filters).",
    ["pii_type"],
)

INJECTION_BYPASSED_TOTAL = _get_or_create_counter(
    "injection_bypassed_total",
    "Total prompt injection attempts that bypassed detection.",
)

SAFETY_CHECKS_TOTAL = _get_or_create_counter(
    "safety_checks_total",
    "Total content safety checks performed.",
    ["layer"],
)

RATE_LIMIT_HITS_TOTAL = _get_or_create_counter(
    "rate_limit_hits_total",
    "Total rate limit hits by user.",
    ["limit_type"],
)

WEB_VITALS_LCP = _get_or_create_histogram(
    "web_vitals_lcp_seconds",
    "Largest Contentful Paint in seconds.",
    ["rating"],
    buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
)

WEB_VITALS_CLS = _get_or_create_histogram(
    "web_vitals_cls_score",
    "Cumulative Layout Shift score.",
    ["rating"],
    buckets=(0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.5, 1.0),
)

WEB_VITALS_FID = _get_or_create_histogram(
    "web_vitals_fid_seconds",
    "First Input Delay in seconds.",
    ["rating"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

WEB_VITALS_FCP = _get_or_create_histogram(
    "web_vitals_fcp_seconds",
    "First Contentful Paint in seconds.",
    ["rating"],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0),
)

WEB_VITALS_TTFB = _get_or_create_histogram(
    "web_vitals_ttfb_seconds",
    "Time to First Byte in seconds.",
    ["rating"],
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
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


def record_answer_correctness(agent_type: str, score: float) -> None:
    """Set the answer correctness gauge for an agent type."""
    ANSWER_CORRECTNESS.labels(agent_type=agent_type).set(score)


def observe_agent_latency(agent_type: str, duration: float) -> None:
    """Observe agent execution latency in seconds."""
    AGENT_LATENCY_SECONDS.labels(agent_type=agent_type).observe(duration)


def set_token_efficiency(agent: str, ratio: float) -> None:
    """Set the token efficiency ratio for an agent."""
    TOKEN_EFFICIENCY.labels(agent=agent).set(ratio)


def record_tokens_total(count: int) -> None:
    """Increment the total tokens consumed counter."""
    TOKENS_TOTAL.inc(count)


def record_cache_hit(cache_name: str) -> None:
    """Increment the cache hits counter for a named cache."""
    CACHE_HITS_TOTAL.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str) -> None:
    """Increment the cache misses counter for a named cache."""
    CACHE_MISSES_TOTAL.labels(cache_name=cache_name).inc()


def record_high_cost_request(agent: str) -> None:
    """Increment the high cost requests counter for an agent."""
    HIGH_COST_REQUESTS_TOTAL.labels(agent=agent).inc()


def record_safety_block(layer: str, reason: str) -> None:
    """Increment the safety blocks counter with layer and reason labels."""
    SAFETY_BLOCKS_TOTAL.labels(layer=layer, reason=reason).inc()


def record_pii_detection(pii_type: str, source: str) -> None:
    """Increment the PII detections counter by type and source."""
    PII_DETECTIONS_TOTAL.labels(pii_type=pii_type, source=source).inc()


def record_injection_attempt() -> None:
    INJECTION_ATTEMPTS_TOTAL.inc()


def record_pii_breach(pii_type: str) -> None:
    PII_BREACHES_TOTAL.labels(pii_type=pii_type).inc()


def record_injection_bypassed() -> None:
    INJECTION_BYPASSED_TOTAL.inc()


def record_safety_check(layer: str) -> None:
    SAFETY_CHECKS_TOTAL.labels(layer=layer).inc()


def record_rate_limit_hit(limit_type: str) -> None:
    """Increment the rate limit hits counter by limit type."""
    RATE_LIMIT_HITS_TOTAL.labels(limit_type=limit_type).inc()


def record_web_vital(metric: str, value: float, rating: str) -> None:
    if metric == "LCP":
        WEB_VITALS_LCP.labels(rating=rating).observe(value)
    elif metric == "CLS":
        WEB_VITALS_CLS.labels(rating=rating).observe(value)
    elif metric == "FID":
        WEB_VITALS_FID.labels(rating=rating).observe(value)
    elif metric == "FCP":
        WEB_VITALS_FCP.labels(rating=rating).observe(value)
    elif metric == "TTFB":
        WEB_VITALS_TTFB.labels(rating=rating).observe(value)


def get_metrics_response() -> tuple[bytes, str]:
    """Generate the latest Prometheus metrics payload."""
    return generate_latest(), CONTENT_TYPE_LATEST
