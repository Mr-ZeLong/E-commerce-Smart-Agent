#!/usr/bin/env bash
#
# validate-monitoring.sh
#
# Validates all monitoring configuration files including Prometheus rules,
# Prometheus configuration, Grafana dashboards, and datasource definitions.
#
# Usage:
#   ./scripts/validate-monitoring.sh
#
# Returns non-zero exit code if any validation fails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

FAILED=0
TOTAL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pass() {
    echo "  ✓ $1"
}

fail() {
    echo "  ✗ $1"
    FAILED=$((FAILED + 1))
}

info() {
    echo ""
    echo "▶ $1"
}

# ---------------------------------------------------------------------------
# 1. Validate Prometheus alert rules
# ---------------------------------------------------------------------------

info "Validating Prometheus alert rules"

if command -v promtool >/dev/null 2>&1; then
    for f in prometheus/*.yml; do
        TOTAL=$((TOTAL + 1))
        if promtool check rules "$f" >/dev/null 2>&1; then
            pass "$(basename "$f")"
        else
            fail "$(basename "$f") — promtool check rules failed"
        fi
    done
else
    echo "  ⚠ promtool not found, skipping Prometheus rule validation"
    echo "    Install from: https://prometheus.io/download/"
fi

# ---------------------------------------------------------------------------
# 2. Validate Prometheus configuration
# ---------------------------------------------------------------------------

info "Validating Prometheus configuration"

if command -v promtool >/dev/null 2>&1; then
    TOTAL=$((TOTAL + 1))
    if promtool check config prometheus/prometheus.yml >/dev/null 2>&1; then
        pass "prometheus.yml"
    else
        fail "prometheus.yml — promtool check config failed"
    fi
else
    echo "  ⚠ promtool not found, skipping Prometheus config validation"
fi

# ---------------------------------------------------------------------------
# 3. Validate Grafana dashboard JSON files
# ---------------------------------------------------------------------------

info "Validating Grafana dashboards"

if command -v jq >/dev/null 2>&1; then
    for f in grafana/dashboards/*.json; do
        TOTAL=$((TOTAL + 1))
        BASENAME=$(basename "$f")

        # Valid JSON
        if ! jq empty "$f" >/dev/null 2>&1; then
            fail "$BASENAME — invalid JSON"
            continue
        fi

        # Required fields
        MISSING=""
        for field in title uid panels timezone; do
            if ! jq -e ".${field}" "$f" >/dev/null 2>&1; then
                MISSING="${MISSING}${field} "
            fi
        done

        if [ -n "$MISSING" ]; then
            fail "$BASENAME — missing required fields: ${MISSING}"
            continue
        fi

        # Panels must be non-empty array
        PANELS_COUNT=$(jq '.panels | length' "$f")
        if [ "$PANELS_COUNT" -eq 0 ]; then
            fail "$BASENAME — has no panels"
            continue
        fi

        pass "$BASENAME"
    done

    # Check UIDs are unique
    TOTAL=$((TOTAL + 1))
    UIDS=$(jq -r '.uid' grafana/dashboards/*.json | sort)
    DUPLICATES=$(echo "$UIDS" | uniq -d)
    if [ -n "$DUPLICATES" ]; then
        fail "Duplicate dashboard UIDs found: $DUPLICATES"
    else
        pass "All dashboard UIDs are unique"
    fi
else
    echo "  ⚠ jq not found, skipping dashboard validation"
    echo "    Install with: apt-get install jq  or  brew install jq"
fi

# ---------------------------------------------------------------------------
# 4. Validate Grafana datasource YAML files
# ---------------------------------------------------------------------------

info "Validating Grafana datasources"

if command -v python3 >/dev/null 2>&1; then
    for f in grafana/provisioning/datasources/*.yml; do
        TOTAL=$((TOTAL + 1))
        BASENAME=$(basename "$f")

        if ! python3 -c "import yaml; yaml.safe_load(open('$f'))" >/dev/null 2>&1; then
            fail "$BASENAME — invalid YAML"
            continue
        fi

        if ! python3 -c "import yaml; d=yaml.safe_load(open('$f')); exit(0 if 'apiVersion' in d else 1)" >/dev/null 2>&1; then
            fail "$BASENAME — missing apiVersion"
            continue
        fi

        if ! python3 -c "import yaml; d=yaml.safe_load(open('$f')); exit(0 if 'datasources' in d else 1)" >/dev/null 2>&1; then
            fail "$BASENAME — missing datasources key"
            continue
        fi

        pass "$BASENAME"
    done

    # Check datasource names are unique
    TOTAL=$((TOTAL + 1))
    python3 << 'PYEOF'
import yaml, glob, sys

names = []
for f in glob.glob('grafana/provisioning/datasources/*.yml'):
    with open(f) as fh:
        data = yaml.safe_load(fh)
        for ds in data.get('datasources', []):
            names.append(ds.get('name', ''))

seen = set()
duplicates = set()
for name in names:
    if name in seen:
        duplicates.add(name)
    seen.add(name)

if duplicates:
    print(f"Duplicate datasource names: {', '.join(sorted(duplicates))}")
    sys.exit(1)
PYEOF
    if [ $? -eq 0 ]; then
        pass "All datasource names are unique"
    else
        fail "Duplicate datasource names found"
    fi
else
    echo "  ⚠ python3 not found, skipping datasource validation"
fi

# ---------------------------------------------------------------------------
# 5. Validate alertmanager configuration
# ---------------------------------------------------------------------------

info "Validating Alertmanager configuration"

TOTAL=$((TOTAL + 1))
if command -v amtool >/dev/null 2>&1; then
    if amtool check-config alertmanager/alertmanager.yml >/dev/null 2>&1; then
        pass "alertmanager.yml"
    else
        fail "alertmanager.yml — amtool check-config failed"
    fi
else
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import yaml; yaml.safe_load(open('alertmanager/alertmanager.yml'))" >/dev/null 2>&1; then
            pass "alertmanager.yml (YAML syntax only — install amtool for full validation)"
        else
            fail "alertmanager.yml — invalid YAML"
        fi
    else
        echo "  ⚠ Neither amtool nor python3 found, skipping alertmanager validation"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "─────────────────────────────────────────"
echo "  Validation complete: $((TOTAL - FAILED))/$TOTAL passed"
echo "─────────────────────────────────────────"

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "ERROR: $FAILED validation(s) failed"
    exit 1
fi

echo ""
echo "All monitoring configurations are valid."
exit 0
