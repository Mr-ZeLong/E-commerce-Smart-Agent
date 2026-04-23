# Alert Response Runbook

This document describes standard operating procedures for responding to alerts produced by the E-commerce Smart Agent observability system.

## Alert Severity Definitions

| Severity | Meaning | Response Time | SLA |
|----------|---------|---------------|-----|
| **P0** | Critical – service degradation or data loss imminent | Immediate (15 min) | 99.99% uptime |
| **P1** | Warning – significant impact on user experience | Within 1 hour | 99.9% uptime |
| **P2** | Info – anomaly detected, monitoring required | Within 4 hours | Best effort |

## Alert Channels

The system supports the following notification channels:

| Channel | Configuration | Use Case |
|---------|--------------|----------|
| **Email** | `ALERT_ADMIN_EMAILS` in config | Default for all severities |
| **Webhook** | Per-rule webhook URL | Generic integration (Slack, Teams, etc.) |
| **PagerDuty** | Routing key per rule | P0/P1 escalation |
| **OpsGenie** | API key per rule | P0/P1 escalation |

## Default Alert Rules

The following rules are created automatically on first startup:

| Rule | Metric | Threshold | Severity | Auto-Resolve |
|------|--------|-----------|----------|--------------|
| `high_latency` | avg_latency_ms | > 2000ms | P1 | Yes |
| `high_error_rate` | error_rate | > 1% | P0 | Yes |
| `high_hallucination_rate` | hallucination_rate | > 5% | P1 | Yes |
| `service_unavailable` | health_status | != 200 | P0 | Yes |
| `high_transfer_rate` | transfer_rate | > 30% | P1 | Yes |

## Alert Types and Response Procedures

### high_latency (P1)

**Trigger:** End-to-end chat latency exceeds 2000 ms.

**Response:**
1. Check the `chat_latency_seconds` Prometheus metric for the offending agent.
2. Review recent deployments or configuration changes.
3. If a single agent is affected, verify its downstream dependencies (database, Redis, LLM API).
4. Scale Celery workers if the bottleneck is async task backlog.
5. Escalate to P0 if latency continues to rise above 5000 ms.

### high_error_rate (P0)

**Trigger:** Chat error rate exceeds 1%.

**Response:**
1. Inspect `chat_errors_total` by `error_type` label.
2. Check application logs for stack traces (use `trace_id` to correlate).
3. If errors are LLM-related, verify API key quotas and upstream service status.
4. If database-related, check connection pool saturation and query timeouts.
5. Consider enabling circuit breaker or fallback responses.
6. Page on-call engineer immediately.

### high_hallucination_rate (P1)

**Trigger:** Hallucination rate exceeds 5%.

**Response:**
1. Review recent RAG retrieval quality (`rag_precision` metric).
2. Verify knowledge base sync status and embedding model health.
3. Check prompt versions in the admin panel for regressions.
4. If hallucinations cluster around a specific intent, temporarily raise the confidence threshold for that intent to force human review.

### service_unavailable (P0)

**Trigger:** Health check endpoint returns non-200 status.

**Response:**
1. Verify infrastructure status (Kubernetes pods, load balancer, database).
2. Check for recent deployments that may have introduced failures.
3. Review `/metrics` endpoint availability.
4. If Redis is unreachable, verify network partitions or memory exhaustion.
5. Initiate incident response protocol and notify stakeholders.

### high_transfer_rate (P1)

**Trigger:** Human transfer rate exceeds the configured threshold (default 30%).

**Response:**
1. Analyze transfer reasons in `human_transfers_total` metric.
2. If transfers are due to low confidence, review the confidence calibration.
3. If transfers spike for a specific intent, check agent configuration and prompt quality for that intent.
4. Consider A/B testing an alternative prompt or routing rule.

## Auto-Healing Behaviors

The system includes self-healing Celery tasks that run on a schedule:

| Task | Schedule | Action |
|------|----------|--------|
| `autoheal.check_celery_workers` | Every 5 minutes | Shuts down workers with > 1 hour uptime and active tasks |
| `autoheal.clear_redis_cache` | Every 10 minutes | Removes `cache:*`, `rate_limit:*`, `temp:*` keys when Redis memory > 512 MB |
| `autoheal.restart_stuck_workers` | Every 5 minutes | Detects and restarts stuck Celery workers |
| `autoheal.clear_expired_redis_keys` | Every 10 minutes | Clears temporary Redis keys when memory exceeds threshold |
| `autoheal.check_db_pool_health` | Every 5 minutes | Monitors database connection pool saturation |
| `alerting.evaluate_rules` | Every 1 minute | Evaluates alert rules against current metrics |
| `alerting.check_service_health` | Every 30 seconds | Performs health check and fires P0 if unhealthy |

**Note:** Auto-healing is a mitigation, not a root-cause fix. Always investigate why workers became stuck or Redis memory grew.

## Manual Alert Operations

Administrators can perform the following actions via the Admin API (`/api/v1/admin/alerts`):

### Acknowledge an Alert
```bash
curl -X POST /api/v1/admin/alerts/events/{event_id}/acknowledge \
  -H "Authorization: Bearer $TOKEN"
```

### Resolve an Alert
```bash
curl -X POST /api/v1/admin/alerts/events/{event_id}/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"reason": "Fixed by restarting the LLM service"}'
```

### Manually Trigger an Alert
```bash
curl -X POST /api/v1/admin/alerts/trigger?rule_id=1 \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"metric_value": 5000, "message": "Manual test alert"}'
```

### Create a Custom Rule
```bash
curl -X POST /api/v1/admin/alerts/rules \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "custom_latency_alert",
    "metric": "avg_latency_ms",
    "operator": "gt",
    "threshold": 3000,
    "severity": "P1",
    "duration_seconds": 120
  }'
```

## Escalation Matrix

| Severity | First Responder | Escalation (30 min) | Escalation (1 hour) |
|----------|----------------|---------------------|---------------------|
| P0 | On-call engineer | Engineering manager | CTO |
| P1 | On-call engineer | Engineering manager | - |
| P2 | Operations team | - | - |

## Contact

- Primary on-call: configured via `ALERT_ADMIN_EMAILS`
- Slack channel: #alerts-ecommerce-agent
- Incident commander rotation: see PagerDuty schedule
