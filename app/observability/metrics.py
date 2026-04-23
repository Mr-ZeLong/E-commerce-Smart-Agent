"""Prometheus metrics for the E-commerce Smart Agent.

Provides custom application metrics alongside the existing OpenTelemetry tracing.
All metric recording functions are async-safe and non-blocking.
"""

from __future__ import annotations

from prometheus_client import (  # type: ignore[import-not-found] - prometheus-client is installed but lacks stubs
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

CHAT_REQUESTS_TOTAL = Counter(
    "chat_requests_total",
    "Total number of chat requests received.",
    ["intent_category", "final_agent"],
)

CHAT_ERRORS_TOTAL = Counter(
    "chat_errors_total",
    "Total number of chat request errors.",
    ["error_type"],
)

CHAT_LATENCY_SECONDS = Histogram(
    "chat_latency_seconds",
    "End-to-end chat request latency in seconds.",
    ["final_agent"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

NODE_LATENCY_SECONDS = Histogram(
    "node_latency_seconds",
    "Individual graph node execution latency in seconds.",
    ["node_name"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TOKEN_USAGE_TOTAL = Counter(
    "token_usage_total",
    "Total number of tokens consumed by LLM calls.",
    ["agent"],
)

CONTEXT_UTILIZATION_RATIO = Gauge(
    "context_utilization_ratio",
    "Ratio of context tokens used vs budget (0.0-1.0).",
)

HUMAN_TRANSFERS_TOTAL = Counter(
    "human_transfers_total",
    "Total number of requests transferred to human agents.",
    ["reason"],
)

INTENT_ACCURACY = Gauge(
    "intent_accuracy",
    "Accuracy of intent classification (0.0-1.0).",
    ["intent_category"],
)

RAG_PRECISION = Gauge(
    "rag_precision",
    "Precision of RAG retrieval (0.0-1.0).",
)

HALLUCINATION_RATE = Gauge(
    "hallucination_rate",
    "Rate of hallucinated responses (0.0-1.0).",
)

CONFIDENCE_SCORE = Histogram(
    "confidence_score",
    "Distribution of confidence scores.",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)


def record_chat_request(
    intent_category: str | None = None,
    final_agent: str | None = None,
) -> None:
    """Increment the chat request counter.

    Args:
        intent_category: Detected primary intent (e.g. ``"ORDER"``).
        final_agent: Name of the agent that handled the request.
    """
    CHAT_REQUESTS_TOTAL.labels(
        intent_category=intent_category or "unknown",
        final_agent=final_agent or "unknown",
    ).inc()


def record_chat_error(error_type: str) -> None:
    """Increment the chat error counter.

    Args:
        error_type: Classification of the error (e.g. ``"runtime"``,
            ``"connection"``, ``"timeout"``).
    """
    CHAT_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_chat_latency(latency_seconds: float, final_agent: str | None = None) -> None:
    """Observe chat end-to-end latency.

    Args:
        latency_seconds: Total latency in seconds.
        final_agent: Name of the agent that handled the request.
    """
    CHAT_LATENCY_SECONDS.labels(final_agent=final_agent or "unknown").observe(latency_seconds)


def record_node_latency(node_name: str, latency_seconds: float) -> None:
    """Observe individual node execution latency.

    Args:
        node_name: Graph node name (e.g. ``"router_node"``).
        latency_seconds: Node latency in seconds.
    """
    NODE_LATENCY_SECONDS.labels(node_name=node_name).observe(latency_seconds)


def record_token_usage(tokens: int, agent: str | None = None) -> None:
    """Record token consumption.

    Args:
        tokens: Number of tokens consumed.
        agent: Agent or component responsible for the LLM call.
    """
    TOKEN_USAGE_TOTAL.labels(agent=agent or "unknown").inc(tokens)


def record_context_utilization(ratio: float) -> None:
    """Set the current context utilization ratio.

    Args:
        ratio: Value between ``0.0`` and ``1.0``.
    """
    CONTEXT_UTILIZATION_RATIO.set(ratio)


def record_human_transfer(reason: str | None = None) -> None:
    """Increment the human transfer counter.

    Args:
        reason: Reason for transfer (e.g. ``"low_confidence"``).
    """
    HUMAN_TRANSFERS_TOTAL.labels(reason=reason or "unknown").inc()


def record_confidence_score(score: float) -> None:
    """Observe a confidence score value.

    Args:
        score: Confidence score between ``0.0`` and ``1.0``.
    """
    CONFIDENCE_SCORE.observe(score)


def set_intent_accuracy(value: float, intent_category: str | None = None) -> None:
    """Set the intent classification accuracy gauge.

    Args:
        value: Accuracy between ``0.0`` and ``1.0``.
        intent_category: Optional intent category label.
    """
    INTENT_ACCURACY.labels(intent_category=intent_category or "overall").set(value)


def set_rag_precision(value: float) -> None:
    """Set the RAG precision gauge.

    Args:
        value: Precision between ``0.0`` and ``1.0``.
    """
    RAG_PRECISION.set(value)


def set_hallucination_rate(value: float) -> None:
    """Set the hallucination rate gauge.

    Args:
        value: Rate between ``0.0`` and ``1.0``.
    """
    HALLUCINATION_RATE.set(value)


def get_metrics_response() -> tuple[bytes, str]:
    """Generate the latest Prometheus metrics payload.

    Returns:
        A tuple of ``(body, content_type)`` suitable for a HTTP response.
    """
    return generate_latest(), CONTENT_TYPE_LATEST
