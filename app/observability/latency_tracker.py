"""Latency trend tracker for graph node execution."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine.row import Row as SQLRow
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.observability import GraphNodeLog

logger = logging.getLogger(__name__)


def _compute_percentile(values: list[float], percentile: float) -> float:
    """Compute a percentile from a sorted list of values using linear interpolation.

    Args:
        values: Sorted list of float values.
        percentile: Percentile to compute (0.0–1.0).

    Returns:
        The interpolated percentile value, or 0.0 if the list is empty.
    """
    if not values:
        return 0.0

    n = len(values)
    if n == 1:
        return values[0]

    index = (n - 1) * percentile
    lower = int(index)
    upper = lower + 1
    if upper >= n:
        return values[-1]

    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


async def compute_node_latency_stats(
    session: AsyncSession,
    node_name: str | None = None,
) -> dict[str, Any]:
    """Compute latency statistics per node from GraphNodeLog records.

    Calculates TTFT (time to first token, approximated by minimum latency),
    p50, p95, and p99 latency percentiles for each node or a specific node.

    Args:
        session: Async database session for querying.
        node_name: Optional specific node name to filter by. If None,
            statistics are computed for all nodes grouped by node name.

    Returns:
        A dictionary mapping node names to their latency statistics,
        or a single entry when ``node_name`` is provided.
    """
    stmt = select(GraphNodeLog)
    if node_name is not None:
        stmt = stmt.where(GraphNodeLog.node_name == node_name)  # type: ignore - SQLModel field comparison typing issue with ty

    try:
        result = await session.exec(stmt)  # type: ignore - SQLModel async exec typing issue with ty
        rows = result.all()
    except Exception as e:  # noqa: BLE001
        logger.warning("Database query failed during latency tracking: %s", e)
        return {}

    if not rows:
        logger.warning("No GraphNodeLog records found for latency tracking.")
        return {}

    node_latencies: dict[str, list[float]] = {}
    for row in rows:
        model = row[0] if isinstance(row, SQLRow) else row
        name = model.node_name
        latencies = node_latencies.setdefault(name, [])
        latencies.append(float(model.latency_ms))

    stats: dict[str, Any] = {}
    for name, latencies in node_latencies.items():
        sorted_latencies = sorted(latencies)
        count = len(sorted_latencies)
        total_ms = sum(sorted_latencies)

        stats[name] = {
            "count": count,
            "total_ms": total_ms,
            "mean_ms": total_ms / count if count > 0 else 0.0,
            "ttft_ms": sorted_latencies[0] if sorted_latencies else 0.0,
            "p50_ms": _compute_percentile(sorted_latencies, 0.50),
            "p95_ms": _compute_percentile(sorted_latencies, 0.95),
            "p99_ms": _compute_percentile(sorted_latencies, 0.99),
            "min_ms": sorted_latencies[0] if sorted_latencies else 0.0,
            "max_ms": sorted_latencies[-1] if sorted_latencies else 0.0,
        }

    return stats
