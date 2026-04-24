"""Test suite for alert rules migration validation."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
GRAFANA_ALERTING_DIR = PROJECT_ROOT / "grafana" / "provisioning" / "alerting"
PROMETHEUS_RULES_FILE = PROJECT_ROOT / "prometheus" / "alert_rules.yml"


class TestAlertRulesMigration:
    """Test suite for alert rules migration from Prometheus to Grafana."""

    def test_prometheus_rules_file_exists(self) -> None:
        """Verify Prometheus alert rules file exists and is readable."""
        assert PROMETHEUS_RULES_FILE.exists(), (
            f"Prometheus rules file not found: {PROMETHEUS_RULES_FILE}"
        )
        content = PROMETHEUS_RULES_FILE.read_text()
        assert "DEPRECATED" in content or "deprecated" in content, (
            "Prometheus rules should have deprecation notice"
        )

    def test_grafana_contact_points_file_exists(self) -> None:
        """Verify Grafana contact points provisioning file exists."""
        contact_points_file = GRAFANA_ALERTING_DIR / "contact-points.yml"
        assert contact_points_file.exists(), f"Contact points file not found: {contact_points_file}"

    def test_grafana_notification_policies_file_exists(self) -> None:
        """Verify Grafana notification policies provisioning file exists."""
        notification_file = GRAFANA_ALERTING_DIR / "notification-policies.yml"
        assert notification_file.exists(), (
            f"Notification policies file not found: {notification_file}"
        )

    def test_grafana_alert_rules_file_exists(self) -> None:
        """Verify Grafana alert rules provisioning file exists."""
        rules_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        assert rules_file.exists(), f"Alert rules file not found: {rules_file}"

    def test_contact_points_yaml_valid(self) -> None:
        """Verify contact points YAML is valid and has required structure."""
        contact_points_file = GRAFANA_ALERTING_DIR / "contact-points.yml"
        content = contact_points_file.read_text()
        data = yaml.safe_load(content)

        assert "apiVersion" in data, "Missing apiVersion"
        assert data["apiVersion"] == 1, "apiVersion should be 1"
        assert "contactPoints" in data, "Missing contactPoints"

        contact_points = data["contactPoints"]
        names = [cp["name"] for cp in contact_points]

        assert "email-default" in names, "Missing email-default contact point"
        assert "pagerduty-critical" in names, "Missing pagerduty-critical contact point"
        assert "webhook-default" in names, "Missing webhook-default contact point"
        assert "slack-alerts" in names, "Missing slack-alerts contact point"

    def test_contact_points_have_receivers(self) -> None:
        """Verify each contact point has at least one receiver."""
        contact_points_file = GRAFANA_ALERTING_DIR / "contact-points.yml"
        content = contact_points_file.read_text()
        data = yaml.safe_load(content)

        for cp in data["contactPoints"]:
            assert "receivers" in cp, f"Contact point {cp.get('name')} missing receivers"
            assert len(cp["receivers"]) > 0, f"Contact point {cp.get('name')} has no receivers"

    def test_notification_policies_yaml_valid(self) -> None:
        """Verify notification policies YAML is valid."""
        notification_file = GRAFANA_ALERTING_DIR / "notification-policies.yml"
        content = notification_file.read_text()
        data = yaml.safe_load(content)

        assert "apiVersion" in data, "Missing apiVersion"
        assert "policies" in data, "Missing policies"

        policies = data["policies"]
        assert len(policies) > 0, "No policies defined"

        default_policy = policies[0]
        assert "receiver" in default_policy, "Default policy missing receiver"
        assert "group_by" in default_policy, "Default policy missing group_by"
        assert "group_wait" in default_policy, "Default policy missing group_wait"
        assert "group_interval" in default_policy, "Default policy missing group_interval"
        assert "repeat_interval" in default_policy, "Default policy missing repeat_interval"

    def test_notification_policies_routing(self) -> None:
        """Verify notification policies have correct routing configuration."""
        notification_file = GRAFANA_ALERTING_DIR / "notification-policies.yml"
        content = notification_file.read_text()
        data = yaml.safe_load(content)

        default_policy = data["policies"][0]
        routes = default_policy.get("routes", [])

        critical_routes = [r for r in routes if r.get("match", {}).get("severity") == "critical"]
        assert len(critical_routes) > 0, "Missing critical severity route"

        warning_routes = [r for r in routes if r.get("match", {}).get("severity") == "warning"]
        assert len(warning_routes) > 0, "Missing warning severity route"

        service_down_routes = [
            r for r in routes if r.get("match", {}).get("alertname") == "ServiceDown"
        ]
        assert len(service_down_routes) > 0, "Missing ServiceDown route"

    def test_alert_rules_yaml_valid(self) -> None:
        """Verify alert rules YAML is valid and has required structure."""
        rules_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        content = rules_file.read_text()
        data = yaml.safe_load(content)

        assert "apiVersion" in data, "Missing apiVersion"
        assert "groups" in data, "Missing groups"
        assert len(data["groups"]) > 0, "No alert groups defined"

        group = data["groups"][0]
        assert "name" in group, "Group missing name"
        assert "rules" in group, "Group missing rules"
        assert len(group["rules"]) > 0, "No rules in group"

    def test_all_alert_rules_present(self) -> None:
        rules_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        content = rules_file.read_text()
        data = yaml.safe_load(content)

        rules = data["groups"][0]["rules"]
        rule_titles = [r["title"] for r in rules]

        expected_rules = [
            "High Error Rate",
            "High Latency P95",
            "High Human Transfer Rate",
            "Low Confidence Score",
            "Low Intent Accuracy",
            "High Hallucination Rate",
            "Low RAG Precision",
            "Service Down",
            "SLO Availability Burn Rate (Fast)",
            "SLO Availability Burn Rate (Slow)",
        ]

        for expected in expected_rules:
            assert expected in rule_titles, f"Missing alert rule: {expected}"

        assert len(rules) == 10, f"Expected 10 rules, found {len(rules)}"

    def test_alert_rules_have_required_fields(self) -> None:
        """Verify each alert rule has required fields."""
        rules_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        content = rules_file.read_text()
        data = yaml.safe_load(content)

        rules = data["groups"][0]["rules"]

        for rule in rules:
            assert "uid" in rule, f"Rule {rule.get('title')} missing uid"
            assert "title" in rule, "Rule missing title"
            assert "condition" in rule, f"Rule {rule['title']} missing condition"
            assert "data" in rule, f"Rule {rule['title']} missing data"
            assert "noDataState" in rule, f"Rule {rule['title']} missing noDataState"
            assert "execErrState" in rule, f"Rule {rule['title']} missing execErrState"
            assert "for" in rule, f"Rule {rule['title']} missing for"
            assert "annotations" in rule, f"Rule {rule['title']} missing annotations"
            assert "labels" in rule, f"Rule {rule['title']} missing labels"

            labels = rule["labels"]
            assert "severity" in labels, f"Rule {rule['title']} missing severity label"
            assert "team" in labels, f"Rule {rule['title']} missing team label"
            assert "service" in labels, f"Rule {rule['title']} missing service label"
            assert labels["team"] == "observability", "Team label should be observability"
            assert labels["service"] == "ecommerce-agent", "Service label should be ecommerce-agent"

            annotations = rule["annotations"]
            assert "summary" in annotations, f"Rule {rule['title']} missing summary annotation"
            assert "description" in annotations, (
                f"Rule {rule['title']} missing description annotation"
            )
            assert "runbook_url" in annotations, (
                f"Rule {rule['title']} missing runbook_url annotation"
            )

    def test_alert_rules_uid_format(self) -> None:
        rules_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        content = rules_file.read_text()
        data = yaml.safe_load(content)

        rules = data["groups"][0]["rules"]

        for rule in rules:
            uid = rule["uid"]
            assert uid.startswith("ecommerce-agent-") or uid.startswith("slo-"), (
                f"Rule {rule['title']} UID should start with ecommerce-agent- or slo-"
            )

    def test_alert_rules_evaluation_interval(self) -> None:
        """Verify alert rules use 1m evaluation interval."""
        rules_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        content = rules_file.read_text()
        data = yaml.safe_load(content)

        group = data["groups"][0]
        assert group.get("interval") == "1m", "Group should have 1m evaluation interval"

    def test_critical_alerts_have_pagerduty_route(self) -> None:
        """Verify critical alerts are routed to PagerDuty."""
        notification_file = GRAFANA_ALERTING_DIR / "notification-policies.yml"

        notification_content = notification_file.read_text()
        notification_data = yaml.safe_load(notification_content)

        policies = notification_data["policies"]

        critical_routes = [
            r
            for p in policies
            for r in p.get("routes", [])
            if r.get("match", {}).get("severity") == "critical"
        ]

        assert len(critical_routes) > 0, "No routes configured for critical severity"

        pagerduty_routes = [
            r for r in critical_routes if "pagerduty" in r.get("receiver", "").lower()
        ]
        assert len(pagerduty_routes) > 0, "Critical alerts not routed to PagerDuty"

    def test_service_down_has_immediate_pagerduty(self) -> None:
        """Verify ServiceDown alert is routed immediately to PagerDuty."""
        notification_file = GRAFANA_ALERTING_DIR / "notification-policies.yml"
        content = notification_file.read_text()
        data = yaml.safe_load(content)

        policies = data["policies"]

        service_down_routes = [
            r
            for p in policies
            for r in p.get("routes", [])
            if r.get("match", {}).get("alertname") == "ServiceDown"
        ]

        assert len(service_down_routes) > 0, "No routes for ServiceDown"

        pagerduty_routes = [
            r for r in service_down_routes if "pagerduty" in r.get("receiver", "").lower()
        ]
        assert len(pagerduty_routes) > 0, "ServiceDown not routed to PagerDuty"


class TestAlertRulesConsistency:
    """Tests to ensure Prometheus and Grafana rules are consistent."""

    def test_prometheus_rules_preserved(self) -> None:
        """Verify Prometheus rules are preserved for fallback period."""
        assert PROMETHEUS_RULES_FILE.exists(), "Prometheus rules file should exist"
        content = PROMETHEUS_RULES_FILE.read_text()
        data = yaml.safe_load(content)

        assert "groups" in data, "Prometheus rules missing groups"

        prometheus_rules = []
        for group in data["groups"]:
            prometheus_rules.extend(group.get("rules", []))

        assert len(prometheus_rules) == 8, (
            f"Expected 8 Prometheus rules, found {len(prometheus_rules)}"
        )

    def test_rules_match_between_systems(self) -> None:
        """Verify Grafana rules match Prometheus rules by alert name."""
        prometheus_content = PROMETHEUS_RULES_FILE.read_text()
        prometheus_data = yaml.safe_load(prometheus_content)

        grafana_file = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
        grafana_content = grafana_file.read_text()
        grafana_data = yaml.safe_load(grafana_content)

        prometheus_names = set()
        for group in prometheus_data["groups"]:
            for rule in group.get("rules", []):
                prometheus_names.add(rule.get("alert"))

        grafana_titles = set()
        for rule in grafana_data["groups"][0].get("rules", []):
            grafana_titles.add(rule.get("title"))

        expected_mapping = {
            "HighErrorRate": "High Error Rate",
            "HighLatencyP95": "High Latency P95",
            "HighHumanTransferRate": "High Human Transfer Rate",
            "LowConfidenceScore": "Low Confidence Score",
            "LowIntentAccuracy": "Low Intent Accuracy",
            "HighHallucinationRate": "High Hallucination Rate",
            "LowRagPrecision": "Low RAG Precision",
            "ServiceDown": "Service Down",
        }

        for prom_name, graf_title in expected_mapping.items():
            assert prom_name in prometheus_names, f"Prometheus missing: {prom_name}"
            assert graf_title in grafana_titles, f"Grafana missing: {graf_title}"

    def test_deprecation_notice_in_prometheus_rules(self) -> None:
        """Verify Prometheus rules have deprecation header."""
        content = PROMETHEUS_RULES_FILE.read_text()

        assert "DEPRECATED" in content or "deprecated" in content.lower(), (
            "Prometheus rules should have deprecation notice"
        )
        assert "Grafana Unified Alerting" in content or "grafana" in content.lower(), (
            "Deprecation notice should reference Grafana Unified Alerting"
        )
