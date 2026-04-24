#!/usr/bin/env bash
#
# deploy-monitoring.sh
#
# Deploys the monitoring stack using docker-compose.monitoring.yml.
# Pulls latest images, starts services, and verifies health.
#
# Usage:
#   ./scripts/deploy-monitoring.sh
#
# This script is non-destructive and will not remove existing volumes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.monitoring.yml"

cd "${PROJECT_ROOT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

if [ ! -f "$COMPOSE_FILE" ]; then
    error "Docker Compose file not found: $COMPOSE_FILE"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    error "docker command not found. Please install Docker."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1 && ! docker-compose version >/dev/null 2>&1; then
    error "docker compose plugin not found. Please install Docker Compose."
    exit 1
fi

# Determine docker compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose -f ${COMPOSE_FILE}"
else
    DOCKER_COMPOSE="docker-compose -f ${COMPOSE_FILE}"
fi

# ---------------------------------------------------------------------------
# Pull latest images
# ---------------------------------------------------------------------------

info "Pulling latest monitoring images..."
$DOCKER_COMPOSE pull

# ---------------------------------------------------------------------------
# Deploy services
# ---------------------------------------------------------------------------

info "Starting monitoring services..."
$DOCKER_COMPOSE up -d

# ---------------------------------------------------------------------------
# Wait for services to start
# ---------------------------------------------------------------------------

info "Waiting for services to become healthy..."
sleep 10

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

HEALTH_FAILED=0

info "Checking Prometheus..."
if curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1; then
    info "Prometheus is healthy"
else
    warn "Prometheus health check failed (may still be starting)"
    HEALTH_FAILED=$((HEALTH_FAILED + 1))
fi

info "Checking Grafana..."
if curl -sf http://localhost:3000/api/health >/dev/null 2>&1; then
    info "Grafana is healthy"
else
    warn "Grafana health check failed (may still be starting)"
    HEALTH_FAILED=$((HEALTH_FAILED + 1))
fi

info "Checking Alertmanager..."
if curl -sf http://localhost:9093/-/healthy >/dev/null 2>&1; then
    info "Alertmanager is healthy"
else
    warn "Alertmanager health check failed (may still be starting)"
    HEALTH_FAILED=$((HEALTH_FAILED + 1))
fi

info "Checking Loki..."
if curl -sf http://localhost:3100/ready >/dev/null 2>&1; then
    info "Loki is healthy"
else
    warn "Loki health check failed (may still be starting)"
    HEALTH_FAILED=$((HEALTH_FAILED + 1))
fi

info "Checking Tempo..."
if curl -sf http://localhost:3200/ready >/dev/null 2>&1; then
    info "Tempo is healthy"
else
    warn "Tempo health check failed (may still be starting)"
    HEALTH_FAILED=$((HEALTH_FAILED + 1))
fi

info "Checking Mimir..."
if curl -sf http://localhost:9009/ready >/dev/null 2>&1; then
    info "Mimir is healthy"
else
    warn "Mimir health check failed (may still be starting)"
    HEALTH_FAILED=$((HEALTH_FAILED + 1))
fi

# ---------------------------------------------------------------------------
# Status summary
# ---------------------------------------------------------------------------

echo ""
echo "═══════════════════════════════════════════════════"
echo "           Monitoring Stack Status"
echo "═══════════════════════════════════════════════════"

$DOCKER_COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "───────────────────────────────────────────────────"
echo "  Service URLs"
echo "───────────────────────────────────────────────────"
echo "  Prometheus:     http://localhost:9090"
echo "  Grafana:        http://localhost:3000"
echo "  Alertmanager:   http://localhost:9093"
echo "  Loki:           http://localhost:3100"
echo "  Tempo:          http://localhost:3200"
echo "  Mimir:          http://localhost:9009"
echo "  OTel Collector: http://localhost:4317 (gRPC) / 4318 (HTTP)"
echo "───────────────────────────────────────────────────"

if [ "$HEALTH_FAILED" -gt 0 ]; then
    echo ""
    warn "$HEALTH_FAILED service(s) may still be starting up."
    warn "Run 'docker compose -f docker-compose.monitoring.yml logs -f' to monitor."
    exit 0
fi

info "Monitoring stack deployed successfully!"
exit 0
