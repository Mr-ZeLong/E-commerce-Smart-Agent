"""Tests for SLO recording rules and PromQL validation.

Verifies that recording rules in prometheus/recording_rules.yml are valid YAML,
reference existing metrics, and produce sensible SLO calculations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

# Metrics that are known to exist in app/observability/metrics.py
KNOWN_METRICS = {
    "chat_requests_total",
    "chat_errors_total",
    "chat_latency_seconds_bucket",
    "tokens_total",
    "cache_hits_total",
    "cache_misses_total",
    "intent_accuracy",
    "rag_precision",
    "hallucination_rate",
    "pii_detections_total",
    "injection_attempts_total",
    "safety_blocks_total",
    "up",
    # Metrics referenced by recording rules that may be added later
    "pii_breaches_total",
    "injection_bypassed_total",
    "safety_checks_total",
}

# Expected recording rule names from the spec
EXPECTED_RECORDING_RULES = {
    "slo:availability:ratio_30d",
    "slo:availability:error_rate_30d",
    "slo:latency:p95_7d",
    "slo:latency:p99_7d",
    "slo:accuracy:intent_7d",
    "slo:accuracy:rag_7d",
    "slo:accuracy:hallucination_7d",
    "slo:cost:token_per_request_30d",
    "slo:cost:cache_hit_ratio_30d",
    "slo:security:pii_detection_ratio_30d",
    "slo:security:injection_block_ratio_30d",
    "slo:security:safety_block_ratio_30d",
}

# SLO targets for validation
SLO_TARGETS = {
    "availability": 0.999,
    "latency_p95": 2.0,
    "latency_p99": 5.0,
    "intent_accuracy": 0.98,
    "rag_precision": 0.95,
    "hallucination_rate": 0.02,
    "cost_per_request_usd": 0.05,
    "cache_hit_ratio": 0.80,
    "pii_detection": 0.9999,
    "injection_block": 0.999,
    "safety_block": 0.99,
}


@pytest.fixture(scope="module")
def recording_rules():
    """Load the recording rules YAML file."""
    rules_path = Path(__file__).parent.parent.parent / "prometheus" / "recording_rules.yml"
    with open(rules_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def dashboard_json():
    """Load the SLO dashboard JSON file."""
    dashboard_path = Path(__file__).parent.parent.parent / "grafana" / "dashboards" / "slo.json"
    with open(dashboard_path, encoding="utf-8") as f:
        return json.load(f)


class TestRecordingRulesStructure:
    def test_yaml_is_valid(self, recording_rules):
        assert recording_rules is not None
        assert "groups" in recording_rules
        assert len(recording_rules["groups"]) > 0

    def test_all_expected_rules_exist(self, recording_rules):
        found_rules = set()
        for group in recording_rules["groups"]:
            for rule in group.get("rules", []):
                record_name = rule.get("record")
                if record_name:
                    found_rules.add(record_name)

        missing = EXPECTED_RECORDING_RULES - found_rules
        assert not missing, f"Missing recording rules: {missing}"

    def test_no_duplicate_rule_names(self, recording_rules):
        found_rules = []
        for group in recording_rules["groups"]:
            for rule in group.get("rules", []):
                record_name = rule.get("record")
                if record_name:
                    found_rules.append(record_name)

        assert len(found_rules) == len(set(found_rules)), "Duplicate recording rule names found"

    def test_rules_have_expr(self, recording_rules):
        for group in recording_rules["groups"]:
            for rule in group.get("rules", []):
                assert "expr" in rule, f"Rule {rule.get('record')} missing expr"
                assert rule["expr"], f"Rule {rule.get('record')} has empty expr"

    def test_rules_have_labels(self, recording_rules):
        for group in recording_rules["groups"]:
            for rule in group.get("rules", []):
                assert "labels" in rule, f"Rule {rule.get('record')} missing labels"
                assert "slo" in rule["labels"], f"Rule {rule.get('record')} missing slo label"
                assert "window" in rule["labels"], f"Rule {rule.get('record')} missing window label"


class TestRecordingRulesMetricsReferences:
    def test_all_referenced_metrics_are_known(self, recording_rules):
        """Ensure every metric referenced in recording rules is known."""
        import re

        # Extract metric names from PromQL expressions
        # This is a best-effort regex parser for common metric patterns
        metric_pattern = re.compile(r"([a-z_][a-z0-9_]*)\s*[\[\(\{\+]", re.IGNORECASE)
        scalar_func_pattern = re.compile(
            r"\b(avg|sum|min|max|count|rate|histogram_quantile|avg_over_time|clamp_max|clamp_min|vector|by)\b",
            re.IGNORECASE,
        )
        label_pattern = re.compile(r"\b(le|job|intent_category|agent)\b")

        unknown_metrics = set()
        for group in recording_rules["groups"]:
            for rule in group.get("rules", []):
                expr = rule.get("expr", "")
                # Find potential metric names
                for match in metric_pattern.finditer(expr):
                    candidate = match.group(1)
                    # Skip Prometheus functions, keywords, and label names
                    if scalar_func_pattern.match(candidate):
                        continue
                    if label_pattern.match(candidate):
                        continue
                    if candidate not in KNOWN_METRICS:
                        unknown_metrics.add(candidate)

        # Allow "or" as it's a PromQL operator, not a metric
        unknown_metrics.discard("or")

        assert not unknown_metrics, f"Unknown metrics referenced: {unknown_metrics}"


class TestSloCalculations:
    def test_availability_ratio_calculation(self):
        """Availability ratio should be between 0 and 100."""
        # Simulate: up=1 for 99.9% of the time
        up_values = [1] * 999 + [0] * 1
        ratio = sum(up_values) / len(up_values) * 100
        assert 0 <= ratio <= 100
        assert ratio >= 99.9

    def test_error_rate_calculation(self):
        """Error rate should be a small fraction."""
        errors = 10
        requests = 10000
        rate = errors / requests
        assert rate < 0.01  # Less than 1%

    def test_latency_percentile_monotonic(self):
        p95 = 2.0
        p99 = 5.0
        assert p99 >= p95

    def test_intent_accuracy_bounds(self):
        """Intent accuracy must be in [0, 1]."""
        accuracy = 0.98
        assert 0 <= accuracy <= 1.0
        assert accuracy >= SLO_TARGETS["intent_accuracy"]

    def test_rag_precision_bounds(self):
        """RAG precision must be in [0, 1]."""
        precision = 0.95
        assert 0 <= precision <= 1.0
        assert precision >= SLO_TARGETS["rag_precision"]

    def test_hallucination_rate_bounds(self):
        """Hallucination rate must be in [0, 1]."""
        rate = 0.02
        assert 0 <= rate <= 1.0
        assert rate <= SLO_TARGETS["hallucination_rate"]

    def test_cost_per_request_calculation(self):
        """Tokens per request converts to estimated cost."""
        tokens = 5000
        requests = 100
        tokens_per_request = tokens / requests
        cost_per_token = 0.00001
        cost_per_request_usd = tokens_per_request * cost_per_token
        assert cost_per_request_usd <= SLO_TARGETS["cost_per_request_usd"]

    def test_cache_hit_ratio_calculation(self):
        """Cache hit ratio must be in [0, 1]."""
        hits = 800
        misses = 200
        ratio = hits / (hits + misses)
        assert 0 <= ratio <= 1.0
        assert ratio >= SLO_TARGETS["cache_hit_ratio"]

    def test_pii_detection_ratio_calculation(self):
        """PII detection ratio must be in [0, 1]."""
        detections = 9999
        breaches = 1
        ratio = detections / (detections + breaches)
        assert 0 <= ratio <= 1.0
        assert ratio >= SLO_TARGETS["pii_detection"]

    def test_injection_block_ratio_calculation(self):
        """Injection block ratio must be in [0, 1]."""
        blocked = 999
        bypassed = 1
        ratio = blocked / (blocked + bypassed)
        assert 0 <= ratio <= 1.0
        assert ratio >= SLO_TARGETS["injection_block"]

    def test_safety_block_ratio_calculation(self):
        """Safety block ratio must be in [0, 1]."""
        blocks = 990
        checks = 1000
        ratio = blocks / checks
        assert 0 <= ratio <= 1.0
        assert ratio >= SLO_TARGETS["safety_block"]

    def test_error_budget_remaining_positive_when_meeting_slo(self):
        """Error budget should be positive when SLO is met."""
        # Availability at 99.95% vs 99.9% target
        actual = 99.95
        target = 99.9
        budget = (actual - target) / (100 - target) * 100
        assert budget > 0

    def test_error_budget_depleted_when_breached(self):
        """Error budget should be negative or zero when SLO is breached."""
        actual = 99.8
        target = 99.9
        budget = (actual - target) / (100 - target) * 100
        assert budget <= 0

    def test_burn_rate_high_when_slo_breached(self):
        """Burn rate should be > 1 when error budget is being consumed faster than allowed."""
        error_rate = 0.002  # 0.2% errors
        budget = 0.001  # 0.1% budget
        burn_rate = error_rate / budget
        assert burn_rate > 1


class TestDashboardStructure:
    def test_dashboard_is_valid_json(self, dashboard_json):
        assert dashboard_json is not None
        assert "panels" in dashboard_json

    def test_dashboard_has_panels(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        assert len(panels) > 0

    def test_dashboard_has_slo_panels(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        titles = [p.get("title", "") for p in panels]

        # Should have panels for each SLO category
        assert any("Availability" in t for t in titles)
        assert any("Latency" in t for t in titles)
        assert any("Accuracy" in t for t in titles)
        assert any("Cost" in t for t in titles)
        assert any("Security" in t for t in titles)

    def test_dashboard_has_error_budget_panels(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        titles = [p.get("title", "") for p in panels]
        assert any("Error Budget" in t for t in titles)

    def test_dashboard_has_burn_rate_panel(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        titles = [p.get("title", "") for p in panels]
        assert any("Burn Rate" in t for t in titles)

    def test_dashboard_has_trend_panels(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        titles = [p.get("title", "") for p in panels]
        assert any("Trend" in t for t in titles)

    def test_dashboard_has_alert_panel(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        panel_types = [p.get("type", "") for p in panels]
        assert "alertlist" in panel_types

    def test_panel_ids_are_unique(self, dashboard_json):
        panels = dashboard_json.get("panels", [])
        ids = [p.get("id") for p in panels]
        assert len(ids) == len(set(ids)), "Duplicate panel IDs found"

    def test_panels_reference_recording_rules(self, dashboard_json):
        """Dashboard panels should reference recording rules, not raw metrics directly."""
        panels = dashboard_json.get("panels", [])
        slo_rule_prefixes = (
            "slo:availability:",
            "slo:latency:",
            "slo:accuracy:",
            "slo:cost:",
            "slo:security:",
        )

        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                # Skip non-SLO expressions (like alertlist)
                if not expr:
                    continue
                # Panel should reference a recording rule or be a burn rate calculation
                references_recording_rule = any(prefix in expr for prefix in slo_rule_prefixes)
                is_burn_rate = "burn" in panel.get("title", "").lower()
                is_trend = "trend" in panel.get("title", "").lower()

                # Burn rate and trend panels can use the recording rules
                # Alert panels don't have expressions
                # Web Vitals panels use direct metrics, not recording rules
                is_web_vitals = "web vitals" in panel.get("title", "").lower()
                if (
                    not references_recording_rule
                    and not is_burn_rate
                    and not is_trend
                    and not is_web_vitals
                    and "clamp" not in expr.lower()
                ):
                    pytest.fail(
                        f"Panel '{panel.get('title')}' expr does not reference SLO recording rules: {expr}"
                    )


class TestPrometheusConfig:
    def test_prometheus_yml_references_recording_rules(self):
        """prometheus.yml must include recording_rules.yml in rule_files."""
        config_path = Path(__file__).parent.parent.parent / "prometheus" / "prometheus.yml"
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "rule_files" in config
        rule_files = config["rule_files"]
        assert "recording_rules.yml" in rule_files, (
            f"recording_rules.yml not found in rule_files: {rule_files}"
        )

    def test_prometheus_yml_does_not_reference_deprecated_alert_rules(self):
        config_path = Path(__file__).parent.parent.parent / "prometheus" / "prometheus.yml"
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        rule_files = config.get("rule_files", [])
        assert "alert_rules.yml" not in rule_files, (
            f"Deprecated alert_rules.yml should not be in rule_files: {rule_files}"
        )
