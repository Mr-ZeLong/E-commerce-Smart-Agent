"""Tests for baseline comparison functionality."""

import json

import pytest

from app.evaluation.baseline import (
    ComparisonResult,
    MetricComparison,
    compare_metrics,
    format_comparison,
    load_baseline,
)


def test_load_baseline_success(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    data = {"intent_accuracy": 0.85, "slot_recall": 0.90}
    baseline_path.write_text(json.dumps(data), encoding="utf-8")

    result = load_baseline(baseline_path)
    assert result == data


def test_load_baseline_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_baseline("/nonexistent/baseline.json")


def test_load_baseline_invalid_json(tmp_path):
    baseline_path = tmp_path / "bad.json"
    baseline_path.write_text("not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_baseline(baseline_path)


def test_load_baseline_not_dict(tmp_path):
    baseline_path = tmp_path / "list.json"
    baseline_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_baseline(baseline_path)


def test_compare_metrics_exact_match():
    baseline = {"intent_accuracy": 0.85, "slot_recall": 0.90}
    current = {"intent_accuracy": 0.85, "slot_recall": 0.90}

    result = compare_metrics(current, baseline)
    assert result.passed is True
    assert result.threshold == 0.05
    assert len(result.metrics) == 2
    assert result.metrics["intent_accuracy"].degradation == 0.0
    assert result.metrics["slot_recall"].degradation == 0.0


def test_compare_metrics_degradation_above_threshold():
    baseline = {"intent_accuracy": 0.90}
    current = {"intent_accuracy": 0.84}  # 6.67% degradation

    result = compare_metrics(current, baseline)
    assert result.passed is False
    assert result.metrics["intent_accuracy"].degradation == pytest.approx(0.0667, abs=0.001)
    assert result.metrics["intent_accuracy"].passed is False


def test_compare_metrics_degradation_below_threshold():
    baseline = {"intent_accuracy": 0.90}
    current = {"intent_accuracy": 0.88}  # 2.22% degradation

    result = compare_metrics(current, baseline)
    assert result.passed is True
    assert result.metrics["intent_accuracy"].degradation == pytest.approx(0.0222, abs=0.001)
    assert result.metrics["intent_accuracy"].passed is True


def test_compare_metrics_missing_current():
    baseline = {"intent_accuracy": 0.85, "slot_recall": 0.90}
    current = {"intent_accuracy": 0.85}

    result = compare_metrics(current, baseline)
    assert result.passed is True
    assert "slot_recall" not in result.metrics


def test_compare_metrics_non_numeric_skipped():
    baseline = {"intent_accuracy": 0.85, "model_name": "gpt-4"}
    current = {"intent_accuracy": 0.85, "model_name": "gpt-4"}

    result = compare_metrics(current, baseline)
    assert result.passed is True
    assert len(result.metrics) == 1
    assert "model_name" not in result.metrics


def test_compare_metrics_zero_baseline():
    baseline = {"error_count": 0}
    current = {"error_count": 5}

    result = compare_metrics(current, baseline)
    assert result.passed is False
    assert result.metrics["error_count"].degradation == 1.0


def test_compare_metrics_zero_baseline_zero_current():
    baseline = {"error_count": 0}
    current = {"error_count": 0}

    result = compare_metrics(current, baseline)
    assert result.passed is True
    assert result.metrics["error_count"].degradation == 0.0


def test_compare_metrics_improvement():
    baseline = {"intent_accuracy": 0.80}
    current = {"intent_accuracy": 0.90}  # Improvement

    result = compare_metrics(current, baseline)
    assert result.passed is True
    assert result.metrics["intent_accuracy"].degradation == 0.0


def test_compare_metrics_custom_threshold():
    baseline = {"intent_accuracy": 0.90}
    current = {"intent_accuracy": 0.87}  # 3.33% degradation

    result = compare_metrics(current, baseline, threshold=0.02)
    assert result.passed is False

    result = compare_metrics(current, baseline, threshold=0.05)
    assert result.passed is True


def test_format_comparison_pass():
    result = ComparisonResult(
        passed=True,
        threshold=0.05,
        metrics={
            "intent_accuracy": MetricComparison(
                name="intent_accuracy",
                baseline=0.85,
                current=0.85,
                degradation=0.0,
                passed=True,
            )
        },
    )

    formatted = format_comparison(result)
    assert "PASS" in formatted
    assert "intent_accuracy" in formatted
    assert "0.00%" in formatted


def test_format_comparison_fail():
    result = ComparisonResult(
        passed=False,
        threshold=0.05,
        metrics={
            "intent_accuracy": MetricComparison(
                name="intent_accuracy",
                baseline=0.90,
                current=0.84,
                degradation=0.0667,
                passed=False,
            )
        },
    )

    formatted = format_comparison(result)
    assert "FAIL" in formatted
    assert "6.67%" in formatted
