#!/usr/bin/env python3
"""
Migration Script: Prometheus Alert Rules to Grafana Unified Alerting

This script converts Prometheus Alertmanager alert rules to Grafana Unified Alerting
provisioning format. It serves as documentation and utility for the Phase 3.3 migration.

Usage:
    # Convert existing rules (dry-run)
    python scripts/migrate_alerts.py --dry-run
    
    # Generate fresh Grafana rules from Prometheus config
    python scripts/migrate_alerts.py --input prometheus/alert_rules.yml --output grafana/provisioning/alerting/rules/
    
    # Validate both configurations
    python scripts/migrate_alerts.py --validate

Migration Notes:
    - All 8 alert rules are converted with same conditions and thresholds
    - Contact points reference environment variables for configuration
    - Notification policies maintain severity-based routing
    - Prometheus rules are preserved for 1-sprint fallback period
    
Environment Variables Required:
    - ALERT_ADMIN_EMAILS: Comma-separated list of admin email addresses
    - PAGERDUTY_SERVICE_KEY: PagerDuty integration key for critical alerts
    - ALERT_WEBHOOK_URL: Webhook URL for alert notifications
    - SLACK_WEBHOOK_URL: (Optional) Slack webhook for Slack notifications
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


# Default paths
PROJECT_ROOT = Path(__file__).parent.parent
PROMETHEUS_RULES_FILE = PROJECT_ROOT / "prometheus" / "alert_rules.yml"
GRAFANA_ALERTING_DIR = PROJECT_ROOT / "grafana" / "provisioning" / "alerting"
GRAFANA_RULES_FILE = GRAFANA_ALERTING_DIR / "rules" / "ecommerce-agent.yml"
GRAFANA_CONTACT_POINTS_FILE = GRAFANA_ALERTING_DIR / "contact-points.yml"
GRAFANA_NOTIFICATION_POLICIES_FILE = GRAFANA_ALERTING_DIR / "notification-policies.yml"


class AlertRuleConverter:
    """Converts Prometheus alert rules to Grafana Unified Alerting format."""
    
    # Mapping of Prometheus alert names to Grafana titles
    ALERT_NAME_MAPPING = {
        "HighErrorRate": "High Error Rate",
        "HighLatencyP95": "High Latency P95",
        "HighHumanTransferRate": "High Human Transfer Rate",
        "LowConfidenceScore": "Low Confidence Score",
        "LowIntentAccuracy": "Low Intent Accuracy",
        "HighHallucinationRate": "High Hallucination Rate",
        "LowRagPrecision": "Low RAG Precision",
        "ServiceDown": "Service Down"
    }
    
    # UID prefix for all alerts
    UID_PREFIX = "ecommerce-agent"
    
    def __init__(self, evaluation_interval: str = "1m"):
        """Initialize the converter.
        
        Args:
            evaluation_interval: Default evaluation interval for alert rules.
        """
        self.evaluation_interval = evaluation_interval
    
    def convert_alert_name_to_uid(self, alert_name: str) -> str:
        """Convert Prometheus alert name to Grafana UID format.
        
        Args:
            alert_name: Prometheus alert name (e.g., "HighErrorRate")
            
        Returns:
            Grafana UID (e.g., "ecommerce-agent-high-error-rate")
        """
        # Convert camelCase/PascalCase to kebab-case
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', alert_name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()
        return f"{self.UID_PREFIX}-{s2}"
    
    def convert_duration_to_seconds(self, duration: str) -> int:
        """Convert Prometheus duration to seconds for Grafana.
        
        Args:
            duration: Duration string (e.g., "2m", "10m", "1h")
            
        Returns:
            Duration in seconds.
        """
        match = re.match(r'(\d+)([smhd])', duration)
        if not match:
            return 300  # Default 5m
            
        value, unit = int(match.group(1)), match.group(2)
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        return value * multipliers.get(unit, 60)
    
    def determine_evaluator_type(self, expr: str) -> str:
        """Determine if expression uses > or < comparison.
        
        Args:
            expr: Prometheus expression string.
            
        Returns:
            'gt' for greater than, 'lt' for less than.
        """
        if '<' in expr and '>' not in expr.split('<')[0]:
            return 'lt'
        return 'gt'
    
    def extract_threshold(self, expr: str, evaluator_type: str) -> float:
        """Extract threshold value from expression.
        
        Args:
            expr: Prometheus expression string.
            evaluator_type: 'gt' or 'lt'
            
        Returns:
            Threshold value as float.
        """
        if evaluator_type == 'gt':
            match = re.search(r'>\s*([\d.]+)', expr)
        else:
            match = re.search(r'<\s*([\d.]+)', expr)
        
        if match:
            return float(match.group(1))
        return 0.5  # Default threshold
    
    def convert_rule(self, prometheus_rule: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a single Prometheus alert rule to Grafana format.
        
        Args:
            prometheus_rule: Prometheus alert rule dictionary.
            
        Returns:
            Grafana alert rule dictionary.
        """
        alert_name = prometheus_rule.get('alert', 'unknown')
        expr = prometheus_rule.get('expr', '')
        duration = prometheus_rule.get('for', '5m')
        labels = prometheus_rule.get('labels', {})
        annotations = prometheus_rule.get('annotations', {})
        
        # Convert name and UID
        grafana_title = self.ALERT_NAME_MAPPING.get(alert_name, alert_name)
        uid = self.convert_alert_name_to_uid(alert_name)
        
        # Determine evaluator type and threshold
        evaluator_type = self.determine_evaluator_type(expr)
        threshold = self.extract_threshold(expr, evaluator_type)
        
        # Build Grafana rule
        grafana_rule = {
            "uid": uid,
            "title": grafana_title,
            "condition": "A",
            "data": [
                {
                    "refId": "A",
                    "relativeTimeRange": {
                        "from": self.convert_duration_to_seconds(duration),
                        "to": 0
                    },
                    "datasourceUid": "prometheus",
                    "model": {
                        "expr": expr,
                        "conditions": [
                            {
                                "evaluator": {
                                    "params": [threshold],
                                    "type": evaluator_type
                                },
                                "operator": {
                                    "type": "and"
                                },
                                "query": {
                                    "params": ["A"]
                                },
                                "reducer": {
                                    "type": "last"
                                }
                            }
                        ],
                        "intervalMs": 1000,
                        "maxDataPoints": 100,
                        "refId": "A",
                        "type": "math"
                    }
                }
            ],
            "noDataState": "NoData",
            "execErrState": "Error",
            "for": duration,
            "annotations": {
                "summary": annotations.get('summary', f'{grafana_title} alert'),
                "description": annotations.get('description', f'{grafana_title} condition triggered.'),
                "runbook_url": f"https://wiki.internal/observability/runbooks/{uid.replace('ecommerce-agent-', '')}"
            },
            "labels": {
                "severity": labels.get('severity', 'warning'),
                "team": "observability",
                "service": "ecommerce-agent"
            }
        }
        
        return grafana_rule
    
    def convert_all_rules(self, prometheus_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert all Prometheus rule groups to Grafana format.
        
        Args:
            prometheus_groups: List of Prometheus rule groups.
            
        Returns:
            Grafana alert rule groups configuration.
        """
        grafana_rules = []
        
        for group in prometheus_groups:
            for rule in group.get('rules', []):
                if 'alert' in rule:  # Only convert alerting rules, not recording rules
                    grafana_rules.append(self.convert_rule(rule))
        
        return {
            "apiVersion": 1,
            "groups": [
                {
                    "orgId": 1,
                    "name": "ecommerce-agent-alerts",
                    "folder": "Observability",
                    "interval": self.evaluation_interval,
                    "rules": grafana_rules
                }
            ]
        }


def generate_contact_points() -> Dict[str, Any]:
    """Generate Grafana contact points configuration.
    
    Returns:
        Contact points configuration dictionary.
    """
    return {
        "apiVersion": 1,
        "contactPoints": [
            {
                "orgId": 1,
                "name": "email-default",
                "receivers": [
                    {
                        "uid": "email-default-uid",
                        "type": "email",
                        "settings": {
                            "addresses": "${ALERT_ADMIN_EMAILS:-oncall@example.com}",
                            "singleEmail": False,
                            "subject": "[{{ .Status | toUpper }}] {{ .GroupLabels.alertname }}"
                        },
                        "disableResolveMessage": False
                    }
                ]
            },
            {
                "orgId": 1,
                "name": "pagerduty-critical",
                "receivers": [
                    {
                        "uid": "pagerduty-critical-uid",
                        "type": "pagerduty",
                        "settings": {
                            "integrationKey": "${PAGERDUTY_SERVICE_KEY}",
                            "severity": "critical",
                            "class": "{{ .CommonLabels.severity }}",
                            "component": "{{ .CommonLabels.service }}",
                            "group": "{{ .CommonLabels.team }}",
                            "summary": "{{ .CommonAnnotations.summary }}",
                            "description": "{{ .CommonAnnotations.description }}"
                        },
                        "disableResolveMessage": False
                    }
                ]
            },
            {
                "orgId": 1,
                "name": "webhook-default",
                "receivers": [
                    {
                        "uid": "webhook-default-uid",
                        "type": "webhook",
                        "settings": {
                            "url": "${ALERT_WEBHOOK_URL:-http://localhost:8000/api/v1/admin/alerts/webhook}",
                            "httpMethod": "POST",
                            "maxAlerts": 0,
                            "title": "{{ .Status | toUpper }}: {{ .GroupLabels.alertname }}",
                            "message": "{{ .CommonAnnotations.description }}"
                        },
                        "disableResolveMessage": False
                    }
                ]
            },
            {
                "orgId": 1,
                "name": "slack-alerts",
                "receivers": [
                    {
                        "uid": "slack-alerts-uid",
                        "type": "slack",
                        "settings": {
                            "title": "{{ .Status | toUpper }}: {{ .GroupLabels.alertname }}",
                            "text": "{{ .CommonAnnotations.description }}",
                            "username": "E-commerce Smart Agent Alerts",
                            "icon_emoji": ":warning:",
                            "url": "${SLACK_WEBHOOK_URL:-}"
                        },
                        "disableResolveMessage": False
                    }
                ]
            }
        ],
        "deleteContactPoints": [],
        "templates": []
    }


def generate_notification_policies() -> Dict[str, Any]:
    """Generate Grafana notification policies configuration.
    
    Returns:
        Notification policies configuration dictionary.
    """
    return {
        "apiVersion": 1,
        "policies": [
            {
                "orgId": 1,
                "receiver": "email-default",
                "group_by": ["alertname", "severity", "service", "team"],
                "group_wait": "30s",
                "group_interval": "5m",
                "repeat_interval": "4h",
                "mute_time_windows": [],
                "routes": [
                    {
                        "receiver": "pagerduty-critical",
                        "match": {"severity": "critical"},
                        "continue": True,
                        "group_wait": "10s",
                        "group_interval": "5m",
                        "repeat_interval": "2h"
                    },
                    {
                        "receiver": "email-default",
                        "match": {"severity": "critical"},
                        "continue": True
                    },
                    {
                        "receiver": "email-default",
                        "match": {"severity": "warning"},
                        "continue": True
                    },
                    {
                        "receiver": "webhook-default",
                        "match": {"severity": "warning"},
                        "continue": True
                    },
                    {
                        "receiver": "pagerduty-critical",
                        "match": {"alertname": "ServiceDown"},
                        "continue": True,
                        "group_wait": "5s",
                        "repeat_interval": "30m"
                    },
                    {
                        "receiver": "slack-alerts",
                        "match": {"channel": "slack"},
                        "continue": True
                    }
                ]
            }
        ],
        "muteTimes": [],
        "templates": []
    }


def validate_grafana_config() -> bool:
    """Validate Grafana alerting configuration files.
    
    Returns:
        True if all files are valid, False otherwise.
    """
    all_valid = True
    
    files_to_validate = [
        ("Contact Points", GRAFANA_CONTACT_POINTS_FILE),
        ("Notification Policies", GRAFANA_NOTIFICATION_POLICIES_FILE),
        ("Alert Rules", GRAFANA_RULES_FILE)
    ]
    
    for name, filepath in files_to_validate:
        if not filepath.exists():
            print(f"  [ERROR] {name}: File not found at {filepath}")
            all_valid = False
            continue
            
        try:
            content = filepath.read_text()
            data = yaml.safe_load(content)
            
            if name == "Alert Rules":
                # Validate alert rules structure
                groups = data.get("groups", [])
                if not groups:
                    print(f"  [ERROR] {name}: No groups defined")
                    all_valid = False
                else:
                    rules = groups[0].get("rules", [])
                    if len(rules) != 8:
                        print(f"  [WARNING] {name}: Expected 8 rules, found {len(rules)}")
                    print(f"  [OK] {name}: {len(rules)} rules defined")
            elif name == "Contact Points":
                contact_points = data.get("contactPoints", [])
                required = ["email-default", "pagerduty-critical", "webhook-default", "slack-alerts"]
                names = [cp.get("name") for cp in contact_points]
                missing = set(required) - set(names)
                if missing:
                    print(f"  [ERROR] {name}: Missing contact points: {missing}")
                    all_valid = False
                else:
                    print(f"  [OK] {name}: All required contact points present")
            elif name == "Notification Policies":
                policies = data.get("policies", [])
                if not policies:
                    print(f"  [ERROR] {name}: No policies defined")
                    all_valid = False
                else:
                    routes = policies[0].get("routes", [])
                    print(f"  [OK] {name}: {len(routes)} routing rules defined")
                    
        except yaml.YAMLError as e:
            print(f"  [ERROR] {name}: Invalid YAML - {e}")
            all_valid = False
        except Exception as e:
            print(f"  [ERROR] {name}: Validation error - {e}")
            all_valid = False
    
    return all_valid


def add_deprecation_notice(prometheus_file: Path) -> None:
    """Add deprecation notice to Prometheus alert rules file.
    
    Args:
        prometheus_file: Path to Prometheus alert rules file.
    """
    if not prometheus_file.exists():
        print(f"  [WARNING] Prometheus file not found: {prometheus_file}")
        return
        
    content = prometheus_file.read_text()
    
    # Check if already has deprecation notice
    if "DEPRECATED" in content:
        print("  [INFO] Prometheus rules already have deprecation notice")
        return
    
    deprecation_header = """# =============================================================================
# DEPRECATED: Prometheus Alert Rules
# =============================================================================
# 
# WARNING: These alert rules are deprecated as of Phase 3.3 migration.
# 
# Please use Grafana Unified Alerting instead. The rules below are kept
# for a 1-sprint fallback period only and will be removed in a future release.
#
# New alerting configuration location:
#   - Contact Points: grafana/provisioning/alerting/contact-points.yml
#   - Notification Policies: grafana/provisioning/alerting/notification-policies.yml
#   - Alert Rules: grafana/provisioning/alerting/rules/ecommerce-agent.yml
#
# Migration Date: Auto-generated
# Target Removal: 1 sprint from migration date
# =============================================================================

"""
    
    new_content = deprecation_header + content
    prometheus_file.write_text(new_content)
    print("  [OK] Added deprecation notice to Prometheus rules")


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate Prometheus alert rules to Grafana Unified Alerting"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=PROMETHEUS_RULES_FILE,
        help="Input Prometheus alert rules file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=GRAFANA_ALERTING_DIR,
        help="Output directory for Grafana alerting files"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Perform a dry run without writing files"
    )
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Validate existing Grafana configuration files"
    )
    parser.add_argument(
        "--add-deprecation", "-a",
        action="store_true",
        help="Add deprecation notice to Prometheus rules file"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("  E-commerce Smart Agent - Alert Rules Migration Tool")
    print("  Phase 3.3: Prometheus -> Grafana Unified Alerting")
    print("=" * 70)
    print()
    
    # Validation mode
    if args.validate:
        print("Validating Grafana alerting configuration...")
        if validate_grafana_config():
            print("\n[OK] All configuration files are valid!")
            sys.exit(0)
        else:
            print("\n[ERROR] Some configuration files have issues.")
            sys.exit(1)
    
    # Add deprecation notice
    if args.add_deprecation:
        print("Adding deprecation notice to Prometheus rules...")
        add_deprecation_notice(args.input)
        print()
    
    # Load Prometheus rules
    print(f"Loading Prometheus rules from: {args.input}")
    if not args.input.exists():
        print(f"[ERROR] File not found: {args.input}")
        sys.exit(1)
        
    try:
        prometheus_content = args.input.read_text()
        prometheus_data = yaml.safe_load(prometheus_content)
        prometheus_groups = prometheus_data.get("groups", [])
        
        total_rules = sum(len(g.get("rules", [])) for g in prometheus_groups)
        print(f"  [OK] Loaded {total_rules} rules from {len(prometheus_groups)} group(s)")
    except Exception as e:
        print(f"  [ERROR] Failed to load Prometheus rules: {e}")
        sys.exit(1)
    
    print()
    
    # Convert rules
    print("Converting alert rules to Grafana format...")
    converter = AlertRuleConverter(evaluation_interval="1m")
    
    try:
        grafana_rules = converter.convert_all_rules(prometheus_groups)
        print(f"  [OK] Converted {len(grafana_rules['groups'][0]['rules'])} rules")
    except Exception as e:
        print(f"  [ERROR] Failed to convert rules: {e}")
        sys.exit(1)
    
    print()
    
    # Generate additional configurations
    print("Generating contact points and notification policies...")
    contact_points = generate_contact_points()
    notification_policies = generate_notification_policies()
    print("  [OK] Generated configuration templates")
    
    print()
    
    # Output results
    if args.dry_run:
        print("DRY RUN: Would write the following files:")
        print(f"  - {args.output / 'rules' / 'ecommerce-agent.yml'}")
        print(f"  - {args.output / 'contact-points.yml'}")
        print(f"  - {args.output / 'notification-policies.yml'}")
        print()
        print("Configuration preview (first rule):")
        if grafana_rules['groups'][0]['rules']:
            first_rule = grafana_rules['groups'][0]['rules'][0]
            print(yaml.dump(first_rule, default_flow_style=False, indent=2))
    else:
        # Create output directories
        rules_dir = args.output / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Write files
        try:
            rules_file = rules_dir / "ecommerce-agent.yml"
            with open(rules_file, 'w') as f:
                yaml.dump(grafana_rules, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"  [OK] Wrote: {rules_file}")
            
            cp_file = args.output / "contact-points.yml"
            with open(cp_file, 'w') as f:
                yaml.dump(contact_points, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"  [OK] Wrote: {cp_file}")
            
            np_file = args.output / "notification-policies.yml"
            with open(np_file, 'w') as f:
                yaml.dump(notification_policies, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"  [OK] Wrote: {np_file}")
            
            print()
            print("=" * 70)
            print("  Migration complete!")
            print("=" * 70)
            print()
            print("Next steps:")
            print("  1. Review generated files in grafana/provisioning/alerting/")
            print("  2. Configure environment variables in .env:")
            print("     - ALERT_ADMIN_EMAILS")
            print("     - PAGERDUTY_SERVICE_KEY")
            print("     - ALERT_WEBHOOK_URL")
            print("     - SLACK_WEBHOOK_URL (optional)")
            print("  3. Restart Grafana to load provisioning files")
            print("  4. Run validation: python scripts/migrate_alerts.py --validate")
            print()
            print("  Note: Prometheus rules preserved for 1-sprint fallback period")
            print()
            
        except Exception as e:
            print(f"  [ERROR] Failed to write files: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
