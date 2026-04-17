"""Containment Rate evaluation metric for graph execution logs."""

from __future__ import annotations

import logging

from app.models.observability import GraphExecutionLog

logger = logging.getLogger(__name__)


def containment_rate(records: list[GraphExecutionLog]) -> float:
    """Calculate the containment rate from graph execution logs.

    Containment rate measures the proportion of sessions that were handled
    entirely by the agent without requiring human transfer. It is computed
    as ``1 - (transfers / total_sessions)``.

    Args:
        records: List of GraphExecutionLog records to analyze.

    Returns:
        A float between 0.0 and 1.0 representing the containment rate.
    """
    if not records:
        logger.warning("No records provided for containment rate; returning 0.0.")
        return 0.0

    total_sessions = len(records)
    transfers = sum(1 for r in records if r.needs_human_transfer)

    return 1.0 - (transfers / total_sessions)
