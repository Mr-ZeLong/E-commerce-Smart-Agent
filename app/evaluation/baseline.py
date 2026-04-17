"""Baseline loader and comparator for evaluation regression testing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DEGRADATION_THRESHOLD = 0.05


@dataclass
class MetricComparison:
    """Comparison result for a single metric."""

    name: str
    baseline: float
    current: float
    degradation: float
    passed: bool


@dataclass
class ComparisonResult:
    """Overall comparison result across all metrics."""

    passed: bool
    metrics: dict[str, MetricComparison]
    threshold: float


def load_baseline(path: str | Path) -> dict[str, Any]:
    """Load baseline metrics from a JSON file.

    Args:
        path: Path to the baseline JSON file.

    Returns:
        Dictionary of metric name to baseline value.

    Raises:
        FileNotFoundError: If the baseline file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        ValueError: If the baseline data is not a dictionary.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Baseline file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Baseline file must contain a JSON object, got {type(data).__name__}")

    return data


def compare_metrics(
    current: dict[str, Any],
    baseline: dict[str, Any],
    threshold: float = DEFAULT_DEGRADATION_THRESHOLD,
) -> ComparisonResult:
    """Compare current evaluation results against a baseline.

    For each numeric metric present in both current and baseline, compute
    the degradation percentage. A metric is considered degraded if the
    current value drops by more than ``threshold`` relative to the baseline.

    Args:
        current: Current evaluation results.
        baseline: Baseline evaluation results.
        threshold: Maximum allowed degradation ratio (default 0.05 = 5%).

    Returns:
        ComparisonResult with per-metric breakdown and overall pass/fail.
    """
    metrics: dict[str, MetricComparison] = {}
    overall_passed = True

    for key, baseline_value in baseline.items():
        if key not in current:
            logger.warning("Metric '%s' missing from current results; skipping.", key)
            continue

        current_value = current[key]
        if not isinstance(baseline_value, (int, float)) or not isinstance(
            current_value, (int, float)
        ):
            logger.warning("Metric '%s' is non-numeric; skipping.", key)
            continue

        baseline_float = float(baseline_value)
        current_float = float(current_value)

        if baseline_float == 0.0:
            degradation = 0.0 if current_float == 0.0 else 1.0
        else:
            degradation = max(0.0, (baseline_float - current_float) / baseline_float)

        metric_passed = degradation <= threshold
        if not metric_passed:
            overall_passed = False

        metrics[key] = MetricComparison(
            name=key,
            baseline=baseline_float,
            current=current_float,
            degradation=degradation,
            passed=metric_passed,
        )

    return ComparisonResult(
        passed=overall_passed,
        metrics=metrics,
        threshold=threshold,
    )


def format_comparison(result: ComparisonResult) -> str:
    """Format a comparison result as a human-readable summary.

    Args:
        result: The comparison result to format.

    Returns:
        Markdown-formatted summary string.
    """
    lines: list[str] = []
    status = "PASS" if result.passed else "FAIL"
    lines.append(f"## Evaluation Result: {status}")
    lines.append("")
    lines.append(f"Threshold: {result.threshold * 100:.1f}%")
    lines.append("")
    lines.append("| Metric | Baseline | Current | Degradation | Status |")
    lines.append("|--------|----------|---------|-------------|--------|")

    for metric in result.metrics.values():
        status_icon = "PASS" if metric.passed else "FAIL"
        lines.append(
            f"| {metric.name} | {metric.baseline:.4f} | {metric.current:.4f} "
            f"| {metric.degradation * 100:.2f}% | {status_icon} |"
        )

    return "\n".join(lines)
