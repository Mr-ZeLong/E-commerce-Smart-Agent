# Incident Response Runbook

This document provides comprehensive incident response procedures for the
E-commerce Smart Agent alerting system.

## Alert Severity Definitions

| Severity | Meaning | Response Time | SLA |
|----------|---------|---------------|-----|
| **P0** | Critical – service degradation or data loss imminent | Immediate (15 min) | 99.9% uptime |
| **P1** | Warning – significant impact on user experience | Within 1 hour | 99.5% uptime |
| **P2** | Info – anomaly detected, monitoring required | Within 4 hours | Best effort |

## Incident Response Lifecycle

### 1. Detection

Alerts are detected through:
- **Automated monitoring**: Celery tasks (`alerts.check_all_metrics`, `alerts.check_latency_alert`, `alerts.check_error_rate_alert`) run every 1-5 minutes
- **Manual checks**: Admin dashboard at `/admin/alerts/events`
- **External monitoring**: Health check endpoint at `/health`

### 2. Triage

1. Check the alert severity and message
2. Verify if the alert is a false positive by checking recent deployments or configuration changes
3. Determine the scope of impact (single user, specific agent, or entire system)
4. Check if auto-healing is already in progress (`autoheal.check_celery_workers`, `autoheal.clear_redis_cache`)

### 3. Response

#### P0 Response (Critical)

1. **Acknowledge the alert** within 15 minutes via admin API or dashboard
2. **Page the on-call engineer** immediately
3. **Check system health**:
   - Verify all services are running (`/health`)
   - Check database connectivity and query performance
   - Verify Redis is responsive
   - Check LLM API quotas and status
4. **Identify the root cause** using OpenTelemetry traces and logs
5. **Apply immediate mitigations**:
   - Enable circuit breaker if LLM API is failing
   - Scale Celery workers if backlog is high
   - Clear Redis cache if memory is exhausted
6. **Communicate** to stakeholders via Slack #alerts-ecommerce-agent
7. **Create a post-mortem** document within 24 hours

#### P1 Response (Warning)

1. **Acknowledge the alert** within 1 hour
2. **Investigate the trend** over the past 24 hours
3. **Check related metrics** for correlation
4. **Apply fixes** if root cause is clear
5. **Schedule a review** if the issue requires deeper investigation
6. **Escalate to P0** if the situation worsens

#### P2 Response (Info)

1. **Monitor the trend** over the past 7 days
2. **Review during regular standup** or weekly review
3. **Create a ticket** for tracking if the anomaly persists
4. **No immediate action required** unless it degrades to P1

### 4. Resolution

1. **Resolve the alert** via admin API or dashboard with a resolution reason
2. **Verify the fix** by checking metrics return to normal
3. **Monitor for 30 minutes** after resolution to ensure stability
4. **Update the incident log** with root cause and fix details

### 5. Post-Mortem

Required for all P0 incidents and recommended for P1 incidents.

Template:
- **Incident ID**: ALERT-YYYYMMDD-NNN
- **Severity**: P0/P1/P2
- **Duration**: Start time to resolution time
- **Impact**: Number of affected users, sessions, or transactions
- **Root Cause**: Technical explanation of what went wrong
- **Detection**: How the alert was triggered
- **Response**: Timeline of actions taken
- **Resolution**: How the issue was fixed
- **Prevention**: Changes to prevent recurrence
- **Action Items**: Specific tasks with owners and deadlines

## Alert Types and Response Procedures

### high_latency (P1)

**Trigger:** End-to-end chat latency exceeds 2000 ms.

**Immediate Actions:**
1. Check the `chat_latency_seconds` Prometheus metric for the offending agent
2. Review recent deployments or configuration changes
3. If a single agent is affected, verify its downstream dependencies (database, Redis, LLM API)
4. Scale Celery workers if the bottleneck is async task backlog

**Escalation:** Escalate to P0 if latency continues to rise above 5000 ms.

### high_error_rate (P0)

**Trigger:** Chat error rate exceeds 1%.

**Immediate Actions:**
1. Inspect `chat_errors_total` by `error_type` label
2. Check application logs for stack traces (use `trace_id` to correlate)
3. If errors are LLM-related, verify API key quotas and upstream service status
4. If database-related, check connection pool saturation and query timeouts
5. Consider enabling circuit breaker or fallback responses
6. Page on-call engineer immediately

### high_hallucination_rate (P1)

**Trigger:** Hallucination rate exceeds 5%.

**Immediate Actions:**
1. Review recent RAG retrieval quality (`rag_precision` metric)
2. Verify knowledge base sync status and embedding model health
3. Check prompt versions in the admin panel for regressions
4. If hallucinations cluster around a specific intent, temporarily raise the confidence threshold for that intent to force human review

### service_unavailable (P0)

**Trigger:** Health check endpoint returns non-200 status.

**Immediate Actions:**
1. Verify infrastructure status (Kubernetes pods, load balancer, database)
2. Check for recent deployments that may have introduced failures
3. Review `/metrics` endpoint availability
4. If Redis is unreachable, verify network partitions or memory exhaustion
5. Initiate incident response protocol and notify stakeholders

### high_transfer_rate (P1)

**Trigger:** Human transfer rate exceeds the configured threshold (default 30%).

**Immediate Actions:**
1. Analyze transfer reasons in `human_transfers_total` metric
2. If transfers are due to low confidence, review the confidence calibration
3. If transfers spike for a specific intent, check agent configuration and prompt quality for that intent
4. Consider A/B testing an alternative prompt or routing rule

### low_confidence (P2)

**Trigger:** Confidence score falls below the configured threshold (default 0.6).

**Immediate Actions:**
1. Monitor the trend; single low scores are expected
2. If sustained, review RAG retrieval overlap and LLM temperature settings
3. Check for new user intents not covered by the current training data

## Auto-Healing Behaviors

The system includes self-healing Celery tasks that run on a schedule:

| Task | Schedule | Action |
|------|----------|--------|
| `autoheal.check_celery_workers` | Every 5 minutes | Shuts down workers with > 1 hour uptime and active tasks |
| `autoheal.clear_redis_cache` | Every 10 minutes | Removes `cache:*`, `rate_limit:*`, `temp:*` keys when Redis memory > 512 MB |
| `alerts.resolve_stale_alerts` | Every hour | Auto-resolves alerts firing for > 24 hours |

**Note:** Auto-healing is a mitigation, not a root-cause fix. Always investigate why workers became stuck or Redis memory grew.

## Alert Management API

### List Alert Rules

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/admin/alerts/rules"
```

### Create Alert Rule

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom_latency",
    "metric": "avg_latency_ms",
    "operator": "gt",
    "threshold": 3000,
    "severity": "P1",
    "duration_seconds": 120
  }' \
  "http://localhost:8000/api/v1/admin/alerts/rules"
```

### Acknowledge Alert

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}' \
  "http://localhost:8000/api/v1/admin/alerts/events/123/acknowledge"
```

### Resolve Alert

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "reason": "Fixed database connection pool"}' \
  "http://localhost:8000/api/v1/admin/alerts/events/123/resolve"
```

## Contact Information

- **Primary on-call**: configured via `ALERT_ADMIN_EMAILS`
- **Slack channel**: #alerts-ecommerce-agent
- **Incident commander rotation**: see PagerDuty schedule
- **Escalation path**: On-call → Team Lead → Engineering Manager → CTO

## Appendix: Alert Channels

The system supports the following notification channels:

| Channel | Configuration | Use Case |
|---------|--------------|----------|
| **Email** | `ALERT_ADMIN_EMAILS` env var | Default for all alerts |
| **Webhook** | `OTEL_EXPORTER_OTLP_ENDPOINT` or custom URL | Integration with internal systems |
| **PagerDuty** | Routing key in rule channels | P0 critical alerts |
| **OpsGenie** | API key in rule channels | Enterprise alerting |

Configure channels per rule using the channels JSON field:

```json
[
  {"channel": "email", "destination": null},
  {"channel": "webhook", "destination": "https://hooks.example.com/alerts"},
  {"channel": "pagerduty", "destination": "routing-key-here"}
]
```