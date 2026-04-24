"""Prometheus query client for metrics dashboard."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def query_prometheus(promql: str, timeout: float = 10.0) -> list[dict[str, Any]]:
    """Execute a PromQL query against the Prometheus HTTP API.

    Returns:
        List of result dictionaries with ``metric`` and ``value``/``values`` keys.
        Empty list if Prometheus is disabled or the query fails.
    """
    if not settings.PROMETHEUS_ENABLED:
        return []

    url = f"{settings.PROMETHEUS_URL}/api/v1/query"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params={"query": promql})
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("Prometheus query failed: %s", exc)
        return []

    if data.get("status") != "success":
        logger.warning("Prometheus query error: %s", data.get("error", "unknown"))
        return []

    result = data.get("data", {}).get("result", [])
    return result if isinstance(result, list) else []


async def query_prometheus_range(
    promql: str,
    start: str,
    end: str,
    step: str = "1h",
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Execute a range query against Prometheus.

    Args:
        promql: PromQL expression.
        start: RFC3339 or unix_timestamp start time.
        end: RFC3339 or unix_timestamp end time.
        step: Query resolution step width.
        timeout: HTTP timeout in seconds.

    Returns:
        List of result dictionaries. Empty list if disabled or query fails.
    """
    if not settings.PROMETHEUS_ENABLED:
        return []

    url = f"{settings.PROMETHEUS_URL}/api/v1/query_range"
    params = {"query": promql, "start": start, "end": end, "step": step}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("Prometheus range query failed: %s", exc)
        return []

    if data.get("status") != "success":
        logger.warning("Prometheus range query error: %s", data.get("error", "unknown"))
        return []

    result = data.get("data", {}).get("result", [])
    return result if isinstance(result, list) else []


def parse_scalar_value(result: list[dict[str, Any]]) -> float | None:
    """Extract a single scalar value from an instant query result."""
    if not result:
        return None
    value = result[0].get("value")
    if value and len(value) >= 2:
        try:
            return float(value[1])
        except (ValueError, TypeError):
            pass
    return None


def parse_vector_values(result: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract labeled vector values from an instant query result."""
    out: list[dict[str, Any]] = []
    for item in result:
        metric = item.get("metric", {})
        value = item.get("value")
        if value and len(value) >= 2:
            try:
                out.append({"labels": metric, "value": float(value[1])})
            except (ValueError, TypeError):
                continue
    return out
