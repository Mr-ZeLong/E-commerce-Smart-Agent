# Phase 1 Monitoring Unification: Detailed Execution Plan

> **Status**: Planning Complete | **Ready for Review**

## Executive Summary

Phase 1 consolidates fragmented monitoring/alerting infrastructure into a unified system. Six tasks across three execution waves, with clear dependencies, acceptance criteria, and rollback strategy.

**Estimated Duration**: 15 person-days (5 dev-days + 3 SRE-days + 7 parallelizable)
**Risk Level**: Medium (mostly additive changes with safe fallbacks)

---

## 1. Dependency Graph & Execution Waves

### Wave 1: Foundation (Parallel - Day 1-3)
All tasks independent. Maximum parallelism.

```
┌─────────────────────────────────────────────────────────────────┐
│                        WAVE 1 (Day 1-3)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Task 1.1     │  │ Task 1.2     │  │ Task 1.4     │          │
│  │ Alert Rule   │  │ Alertmanager │  │ Missing      │          │
│  │ Consolidation│  │ Config       │  │ Metrics      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐                                              │
│  │ Task 1.6     │                                              │
│  │ Loki Stack   │                                              │
│  └──────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        WAVE 2 (Day 4-6)                         │
│  ┌────────────────────────┐  ┌────────────────────────┐        │
│  │ Task 1.3               │  │ Task 1.5               │        │
│  │ AlertService + Celery  │  │ Metrics Export Unify   │        │
│  │ Connection             │  │ (Prometheus Query)     │        │
│  └────────────────────────┘  └────────────────────────┘        │
│         │                              │                       │
│         └──────────────┬───────────────┘                       │
│                        ▼                                       │
│              ┌─────────────────┐                               │
│              │ Integration Test│                               │
│              └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### Wave Dependency Matrix

| Task | Wave | Depends On | Blocks | Parallel With |
|------|------|-----------|--------|--------------|
| 1.1 Alert Rule Consolidation | 1 | None | 1.3 | 1.2, 1.4, 1.6 |
| 1.2 Alertmanager Config | 1 | None | None | 1.1, 1.4, 1.6 |
| 1.4 Missing Metrics | 1 | None | 1.5 | 1.1, 1.2, 1.6 |
| 1.6 Loki Integration | 1 | None | None | 1.1, 1.2, 1.4 |
| 1.3 Celery + AlertService | 2 | 1.1 | None | 1.5 |
| 1.5 Metrics Export Unify | 2 | 1.4 | None | 1.3 |

---

## 2. Detailed Task Specifications

### Task 1.1: Consolidate Alert Rules (2人日)

**Objective**: Eliminate duplicate alert evaluation paths. Retain single source of truth.

#### Files to Modify
| Action | File | Reason |
|--------|------|--------|
| **DELETE** | `app/observability/alerting.py` | Deprecated AlertManager, replaced by AlertService |
| **DELETE** | `app/observability/alert_rules.py` | AlertRuleEngine uses hardcoded rules + deprecated AlertManager |
| **UPDATE** | `app/services/alert_service.py` | Add missing 6th rule from AlertRuleEngine |
| **UPDATE** | `app/observability/AGENTS.md` | Remove references to deleted files |

#### Migration: 6th Rule
AlertRuleEngine has 6 rules; AlertService._DEFAULT_RULES has 5. The missing rule:

```python
# From alert_rules.py - "low_confidence" rule
{
    "name": "low_confidence",
    "description": "Median confidence score below threshold.",
    "metric": "confidence_score",  # Note: needs metric source
    "operator": "lt",
    "threshold": 0.6,
    "duration_seconds": 300,
    "severity": AlertSeverity.P1,
    "suppress_interval_seconds": 300,
    "auto_resolve": True,
}
```

**Problem**: `confidence_score` is not a queryable metric in `_get_metric_value()`. Two options:
- **Option A**: Add confidence score aggregation to `_get_metric_value()` (recommended)
- **Option B**: Skip this rule (if confidence tracking is handled elsewhere)

**Recommended**: Option A - Add `confidence_score` metric query:
```python
if metric == "confidence_score":
    result = session.exec(
        select(func.avg(GraphExecutionLog.confidence_score)).where(
            GraphExecutionLog.created_at >= since,
            GraphExecutionLog.confidence_score.is_not(None),
        )
    )
    val = result.one()
    return (float(val) if val is not None else None), metadata
```

#### Acceptance Criteria
- [ ] `alerting.py` and `alert_rules.py` removed from codebase
- [ ] No import errors anywhere in the project
- [ ] `AlertService._DEFAULT_RULES` contains all 6 migrated rules
- [ ] `pytest` passes after removal
- [ ] Test coverage does not drop below 75%

#### TDD Approach
1. Write test verifying AlertService contains 6 default rules
2. Write test confirming alert_tasks.py can evaluate all 6 rules
3. Remove deprecated files
4. Run tests, fix any breakage
5. Verify no remaining imports of deleted modules

---

### Task 1.2: Configure Alertmanager Targets (1人日)

**Objective**: Route Prometheus-evaluated alerts to notification channels.

#### Files to Modify
| Action | File | Change |
|--------|------|--------|
| **CREATE** | `alertmanager/alertmanager.yml` | Define receivers (email, webhook, pagerduty) |
| **UPDATE** | `prometheus/prometheus.yml` | Set alertmanager target to `alertmanager:9093` |
| **UPDATE** | `docker-compose.monitoring.yml` | Add alertmanager service |

#### alertmanager.yml Design
```yaml
global:
  smtp_smarthost: '${SMTP_HOST:-localhost:587}'
  smtp_from: '${ALERT_EMAIL_FROM:-alerts@example.com}'

templates:
- '/etc/alertmanager/templates/*.tmpl'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'pagerduty-critical'
    continue: true
  - match:
      severity: warning
    receiver: 'email-team'

receivers:
- name: 'default'
  email_configs:
  - to: '${ALERT_ADMIN_EMAILS:-oncall@example.com}'
    subject: '[{{ .Status | toUpper }}] {{ .GroupLabels.alertname }}'

- name: 'email-team'
  email_configs:
  - to: '${ALERT_ADMIN_EMAILS}'

- name: 'pagerduty-critical'
  pagerduty_configs:
  - service_key: '${PAGERDUTY_SERVICE_KEY}'
    severity: critical

inhibit_rules:
- source_match:
    severity: 'critical'
  target_match:
    severity: 'warning'
  equal: ['alertname']
```

#### Acceptance Criteria
- [ ] `docker-compose.monitoring.yml` includes alertmanager service on port 9093
- [ ] `prometheus/prometheus.yml` points to `alertmanager:9093`
- [ ] Alertmanager config validates with `amtool check-config`
- [ ] Prometheus UI shows alertmanager as connected
- [ ] Test alert fires and reaches webhook endpoint (use webhook.site for testing)

#### TDD Approach
1. Create alertmanager config
2. Add alertmanager to docker-compose
3. Update prometheus.yml
4. Run `docker-compose -f docker-compose.monitoring.yml up -d`
5. Trigger test alert via Prometheus UI
6. Verify alertmanager receives and routes alert

---

### Task 1.3: Connect AlertService to Celery (3人日)

**Objective**: `alert_tasks.py` evaluation triggers real notifications via AlertService._notify().

#### Current Problem
- `alert_tasks.py` uses `_fire_alert_sync()` - creates DB record only, NO notifications
- `AlertService.fire_alert()` is async with suppression + notifications
- Celery tasks are sync - cannot directly call async methods

#### Solution Design

**Option A: Sync wrapper in AlertService (Recommended)**
Add `fire_alert_sync()` to AlertService:

```python
def fire_alert_sync(
    self,
    session: Session,  # sync SQLAlchemy session
    rule: AlertRule,
    metric_value: float,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> AlertEvent | None:
    """Synchronous version for Celery tasks."""
    # Use sync Redis client for suppression
    # Create AlertEvent with sync session
    # Call _notify_sync() for notifications
    pass
```

**Option B: Use async_to_sync**
```python
from asgiref.sync import async_to_sync
# In Celery task:
async_to_sync(alert_service.fire_alert)(...)
```
**Cons**: Creates event loop in worker thread, can cause issues with nested loops.

**Recommended**: Option A - Add dedicated sync methods to AlertService.

#### Files to Modify
| Action | File | Change |
|--------|------|--------|
| **UPDATE** | `app/services/alert_service.py` | Add `fire_alert_sync()`, `_notify_sync()`, sync Redis suppression |
| **UPDATE** | `app/tasks/alert_tasks.py` | Replace `_fire_alert_sync()` with `AlertService.fire_alert_sync()` |
| **UPDATE** | `app/tasks/alert_tasks.py` | Track suppression count in return value |

#### Acceptance Criteria
- [ ] `evaluate_alert_rules` task calls `AlertService.fire_alert_sync()`
- [ ] High-severity (P0/P1) alerts trigger email notifications
- [ ] Redis suppression works in sync context
- [ ] `alerts_suppressed` count in task return value is accurate
- [ ] Notifications include: email, webhook (if configured), PagerDuty (if configured)
- [ ] Celery task test mocks notification channels and verifies calls

#### TDD Approach
1. Write test: `test_evaluate_alert_rules_fires_notification()`
2. Write test: `test_alert_suppression_sync_works()`
3. Implement `fire_alert_sync()` in AlertService
4. Update `alert_tasks.py` to use new method
5. Run tests, verify notifications sent

---

### Task 1.4: Add Missing Dashboard Metrics (3人日)

**Objective**: Instrument 11 missing metrics so Grafana dashboards show data.

#### Metric Definitions

Add to `app/observability/metrics.py`:

```python
# 1. Answer correctness score
ANSWER_CORRECTNESS = _get_or_create_gauge(
    "answer_correctness",
    "Answer correctness score from evaluator (0.0-1.0).",
    ["agent_type"],
)

# 2. Agent latency ( Histogram for performance tracking)
AGENT_LATENCY_SECONDS = _get_or_create_histogram(
    "agent_latency_seconds",
    "Agent execution latency in seconds.",
    ["agent_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 3. Token efficiency ratio
TOKEN_EFFICIENCY = _get_or_create_gauge(
    "token_efficiency",
    "Ratio of useful tokens to total tokens (0.0-1.0).",
    ["agent"],
)

# 4. Total tokens (aggregate counter without labels for dashboard)
TOKENS_TOTAL = _get_or_create_counter(
    "tokens_total",
    "Total tokens consumed across all agents.",
)

# 5-6. Cache hit/miss counters
CACHE_HITS_TOTAL = _get_or_create_counter(
    "cache_hits_total",
    "Total cache hits.",
    ["cache_name"],
)

CACHE_MISSES_TOTAL = _get_or_create_counter(
    "cache_misses_total",
    "Total cache misses.",
    ["cache_name"],
)

# 7. High cost request tracking
HIGH_COST_REQUESTS_TOTAL = _get_or_create_counter(
    "high_cost_requests_total",
    "Total requests exceeding cost threshold.",
    ["agent"],
)

# 8. Safety blocks
SAFETY_BLOCKS_TOTAL = _get_or_create_counter(
    "safety_blocks_total",
    "Total content moderation blocks.",
    ["layer", "reason"],
)

# 9. PII detections
PII_DETECTIONS_TOTAL = _get_or_create_counter(
    "pii_detections_total",
    "Total PII detections by type.",
    ["pii_type", "source"],
)

# 10. Injection attempts
INJECTION_ATTEMPTS_TOTAL = _get_or_create_counter(
    "injection_attempts_total",
    "Total prompt injection attempts detected.",
)

# 11. Rate limit hits
RATE_LIMIT_HITS_TOTAL = _get_or_create_counter(
    "rate_limit_hits_total",
    "Total rate limit hits by user.",
    ["limit_type"],
)
```

#### Instrumentation Points

| # | Metric | File | Function | Line | Instrumentation |
|---|--------|------|----------|------|-----------------|
| 1 | `answer_correctness` | `app/evaluation/metrics.py` | `answer_correctness()` | ~222 | `ANSWER_CORRECTNESS.labels(agent_type="...").set(score)` |
| 2 | `agent_latency_seconds` | `app/observability/token_tracker.py` | `log_usage()` | ~46 | Add timing decorator or manual observation |
| 3 | `token_efficiency` | `app/observability/token_tracker.py` | `log_usage()` | ~46 | Calculate ratio, set gauge |
| 4 | `tokens_total` | `app/observability/token_tracker.py` | `log_usage()` | ~46 | `TOKENS_TOTAL.inc(total)` |
| 5-6 | `cache_hits/misses_total` | `app/core/cache.py` | `_record_hit()` / `_record_miss()` | ~59/63 | `CACHE_HITS/MISSES_TOTAL.labels(cache_name=...).inc()` |
| 7 | `high_cost_requests_total` | `app/observability/token_tracker.py` | `get_high_cost_queries()` | ~180 | `HIGH_COST_REQUESTS_TOTAL.inc()` per result |
| 8 | `safety_blocks_total` | `app/safety/output_moderator.py` | `moderate()` | ~97-156 | Increment per layer block |
| 9 | `pii_detections_total` | `app/context/pii_filter.py` | `log_pii_detection()` | ~325 | Increment per detection type |
| 10 | `injection_attempts_total` | `app/safety/output_moderator.py` | `moderate()` | ~97 | If injection detected |
| 11 | `rate_limit_hits_total` | `app/core/limiter.py` | `check_user_rate_limit()` | ~58 | Increment before raising 429 |

#### Acceptance Criteria
- [ ] All 11 metrics defined in `metrics.py`
- [ ] Each metric has a recording function (e.g., `record_answer_correctness()`)
- [ ] All instrumentation points call recording functions
- [ ] `/metrics` endpoint returns all 11 new metrics
- [ ] Tests verify each metric is incremented/observed correctly
- [ ] No duplicate metric definitions (check against existing `token_usage_total`)

#### Important: tokens_total vs token_usage_total
Existing `token_usage_total` has `agent` label. New `tokens_total` is aggregate without labels. Both serve different purposes:
- `token_usage_total{agent="order"}` = per-agent breakdown
- `tokens_total` = global aggregate for cost dashboard

**No conflict** - keep both.

#### TDD Approach
1. For each metric:
   a. Write test: `test_<metric>_is_recorded()`
   b. Add metric definition to metrics.py
   c. Add recording function
   d. Instrument in business logic
   e. Run test
2. Verify `/metrics` endpoint includes all metrics

---

### Task 1.5: Unify Metrics Export (3人日)

**Objective**: Admin API queries Prometheus first, PostgreSQL as fallback.

#### Current State
- 8 dashboard endpoints in `metrics_dashboard.py` query PostgreSQL `GraphExecutionLog`
- No Prometheus query capability
- Dashboards and Grafana show potentially different values

#### Solution Design

**Feature Flag**: `ENABLE_PROMETHEUS_QUERY` (default: False for gradual rollout)

**Architecture**:
```python
async def _query_metric(
    metric_name: str,
    promql: str,
    fallback_query: Callable,
) -> Any:
    if settings.ENABLE_PROMETHEUS_QUERY:
        try:
            return await _query_prometheus(promql)
        except PrometheusError:
            logger.warning("Prometheus query failed, falling back to DB")
    return await fallback_query()
```

#### Files to Modify
| Action | File | Change |
|--------|------|--------|
| **UPDATE** | `app/core/config.py` | Add `ENABLE_PROMETHEUS_QUERY: bool = False` |
| **UPDATE** | `app/api/v1/admin/metrics_dashboard.py` | Add Prometheus query path with fallback |
| **CREATE** | `app/services/prometheus_client.py` | Thin async wrapper around Prometheus HTTP API |

#### Prometheus Query Mapping

| Endpoint | Current (PostgreSQL) | Prometheus Fallback |
|----------|---------------------|---------------------|
| `/dashboard/summary` | Aggregations on GraphExecutionLog | `sum(chat_requests_total)`, `avg(chat_latency_seconds)` |
| `/dashboard/intent-accuracy` | Count by intent | `intent_accuracy` gauge |
| `/dashboard/transfer-reasons` | Count by reason | `human_transfers_total` |
| `/dashboard/token-usage` | Sum tokens | `token_usage_total` or `tokens_total` |
| `/dashboard/latency-trend` | percentile_cont | `histogram_quantile(0.95, chat_latency_seconds)` |
| `/dashboard/rag-precision` | Avg precision | `rag_precision` gauge |
| `/dashboard/hallucination-rate` | Avg rate | `hallucination_rate` gauge |
| `/dashboard/alerts` | AlertEvent query | Keep DB query (alerts are DB-native) |

#### Acceptance Criteria
- [ ] Feature flag `ENABLE_PROMETHEUS_QUERY` exists in settings
- [ ] When flag is True, endpoints query Prometheus first
- [ ] When flag is False, endpoints use existing PostgreSQL queries
- [ ] Prometheus query failures gracefully fallback to PostgreSQL
- [ ] Response format unchanged (frontend compatible)
- [ ] Latency of endpoints with Prometheus < latency with PostgreSQL

#### TDD Approach
1. Write test: `test_dashboard_uses_prometheus_when_enabled()`
2. Write test: `test_dashboard_falls_back_to_db_on_prometheus_error()`
3. Write test: `test_dashboard_uses_db_when_flag_disabled()`
4. Implement Prometheus client wrapper
5. Modify endpoints to use dual-query pattern
6. Verify response format consistency

---

### Task 1.6: Loki Integration (3人日)

**Objective**: Add log aggregation to monitoring stack.

#### Files to Modify
| Action | File | Change |
|--------|------|--------|
| **UPDATE** | `docker-compose.monitoring.yml` | Add Loki + Promtail services |
| **CREATE** | `loki/loki-config.yml` | Loki configuration |
| **CREATE** | `promtail/promtail-config.yml` | Promtail scrape config |
| **CREATE** | `grafana/provisioning/datasources/loki.yml` | Grafana Loki datasource |

#### docker-compose.monitoring.yml Additions
```yaml
  loki:
    image: grafana/loki:3.0.0
    ports:
      - "3100:3100"
    volumes:
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring

  promtail:
    image: grafana/promtail:3.0.0
    volumes:
      - ./promtail/promtail-config.yml:/etc/promtail/config.yml
      - /var/log:/var/log:ro
      - app-logs:/app/logs:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    networks:
      - monitoring

volumes:
  loki-data:
  app-logs:
```

#### Acceptance Criteria
- [ ] `docker-compose -f docker-compose.monitoring.yml up` starts Loki on port 3100
- [ ] Promtail sends logs to Loki
- [ ] Grafana can query Loki via LogQL
- [ ] Application JSON logs appear in Loki
- [ ] LogQL query response time < 2s for 7-day range

#### TDD Approach
1. Create Loki + Promtail configs
2. Add to docker-compose
3. Add Grafana datasource
4. Start stack: `docker-compose -f docker-compose.monitoring.yml up -d`
5. Verify: `curl http://localhost:3100/ready`
6. Query logs in Grafana Explore

---

## 3. Feature Flag Strategy

### Flags Required

| Flag | Default | Purpose | Rollout |
|------|---------|---------|---------|
| `ENABLE_PROMETHEUS_QUERY` | `False` | Task 1.5: Use Prometheus for dashboard metrics | Gradual: per-endpoint |
| `ALERTSERVICE_CELERY_NOTIFY` | `False` | Task 1.3: Enable notifications from Celery tasks | Blue-green: test channel first |
| `ENABLE_LOKI_DATASOURCE` | `False` | Task 1.6: Show Loki in Grafana | Immediate after verification |

### Flag Implementation

```python
# app/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Phase 1 Feature Flags
    ENABLE_PROMETHEUS_QUERY: bool = False
    ALERTSERVICE_CELERY_NOTIFY: bool = False
    ENABLE_LOKI_DATASOURCE: bool = False
    
    # Alertmanager config
    ALERTMANAGER_ENABLED: bool = False
    ALERTMANAGER_URL: str = "http://alertmanager:9093"
```

### Rollout Plan
1. **Week 1**: Deploy with all flags = False (safe baseline)
2. **Week 2**: Enable `ALERTSERVICE_CELERY_NOTIFY` with test email only
3. **Week 3**: Enable `ENABLE_PROMETHEUS_QUERY` for 1 endpoint (e.g., `/dashboard/summary`)
4. **Week 4**: Roll out to remaining endpoints if metrics consistent
5. **Week 5**: Enable `ENABLE_LOKI_DATASOURCE` after log verification

---

## 4. Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Removing alert_rules.py breaks tests** | High | Medium | Search for all imports before removal; run full test suite |
| **Async/sync mismatch in AlertService** | High | High | Add dedicated sync methods; extensive testing with mock Redis |
| **Prometheus queries slower than DB** | Medium | High | Feature flag with instant fallback; benchmark before rollout |
| **Duplicate metric names** | Medium | Low | Audit existing metrics before adding new ones; use different names |
| **Alertmanager config errors cause storms** | Low | High | Start with test channels only; configure inhibition rules |
| **Loki resource consumption** | Medium | Medium | Set retention to 7 days initially; monitor disk usage |
| **Celery task failure cascades** | Medium | High | Add retry logic; use dead letter queue; monitor task failure rate |

### Critical Path Risks

**Risk 1: Async/Sync Bridge (Task 1.3)**
- **Problem**: AlertService is fully async; Celery tasks are sync
- **Mitigation**: Add `fire_alert_sync()` with sync Redis client and sync DB session
- **Test**: Mock Redis and verify suppression works synchronously

**Risk 2: Metric Name Collisions**
- **Problem**: `tokens_total` vs existing `token_usage_total`
- **Mitigation**: Both are valid - `tokens_total` is aggregate, `token_usage_total` is per-agent
- **Verify**: Check Grafana dashboard JSON expects exactly these names

**Risk 3: Threshold Inconsistencies**
- **Problem**: alert_rules.py, AlertService._DEFAULT_RULES, and prometheus/alert_rules.yml have similar but possibly different thresholds
- **Mitigation**: Audit all thresholds; document in AGENTS.md; use single source (AlertRule DB)

---

## 5. Atomic Commit Strategy

### Commit Sequence

```
commit 1: feat(alerting): Remove deprecated alerting.py and alert_rules.py
  - Delete app/observability/alerting.py
  - Delete app/observability/alert_rules.py
  - Update AGENTS.md
  - Remove any imports

commit 2: feat(alerting): Add 6th default rule to AlertService
  - Update app/services/alert_service.py
  - Add confidence_score metric query to alert_tasks.py
  - Add tests

commit 3: feat(alerting): Add sync fire_alert to AlertService for Celery
  - Update app/services/alert_service.py
  - Update app/tasks/alert_tasks.py
  - Add feature flag ALERTSERVICE_CELERY_NOTIFY
  - Add tests

commit 4: feat(metrics): Add 11 missing Prometheus metrics
  - Update app/observability/metrics.py
  - Instrument all business logic files
  - Add recording helper functions
  - Add tests

commit 5: feat(metrics): Add Prometheus query client for dashboard
  - Create app/services/prometheus_client.py
  - Add ENABLE_PROMETHEUS_QUERY flag
  - Update metrics_dashboard.py with dual-query
  - Add tests

commit 6: feat(infra): Add Alertmanager to monitoring stack
  - Create alertmanager/alertmanager.yml
  - Update prometheus/prometheus.yml
  - Update docker-compose.monitoring.yml

commit 7: feat(infra): Add Loki log aggregation
  - Create loki/loki-config.yml
  - Create promtail/promtail-config.yml
  - Create grafana/provisioning/datasources/loki.yml
  - Update docker-compose.monitoring.yml
```

### Commit Rules
- Each commit is independently revertible
- No commit mixes infrastructure + application code
- Tests included in same commit as code changes
- `ruff check` and `ty check` pass before each commit

---

## 6. TDD-Oriented Execution Order

### For Each Task:

1. **Red**: Write failing test
   ```python
   def test_<scenario>_does_<expected>():
       # Setup
       # Execute
       # Assert (will fail initially)
   ```

2. **Green**: Implement minimal code to pass test
   - No refactoring yet
   - Just make the test pass

3. **Refactor**: Clean up while keeping tests green
   - Extract helpers
   - Improve naming
   - Add edge case tests

### Example: Task 1.4 Metric Instrumentation

```python
# Step 1: Red (test fails)
def test_cache_hit_records_metric():
    from app.observability.metrics import CACHE_HITS_TOTAL
    from app.core.cache import CacheManager
    
    cache = CacheManager()
    before = CACHE_HITS_TOTAL.labels(cache_name="test")._value.get()
    cache.get("test", "key")  # miss
    cache.get("test", "key")  # hit
    after = CACHE_HITS_TOTAL.labels(cache_name="test")._value.get()
    assert after - before == 1

# Step 2: Green (add instrumentation)
# In app/core/cache.py:
def _record_hit(self, cache_name: str) -> None:
    self._stats[cache_name]["hits"] += 1
    CACHE_HITS_TOTAL.labels(cache_name=cache_name).inc()  # NEW
    self._maybe_update_ratio(cache_name)

# Step 3: Refactor (extract recording function)
def record_cache_hit(cache_name: str) -> None:
    CACHE_HITS_TOTAL.labels(cache_name=cache_name).inc()
```

---

## 7. Testing Requirements

### New Tests to Write

| Test File | Tests | Coverage Target |
|-----------|-------|-----------------|
| `tests/test_alert_service.py` | Sync fire_alert, suppression, notifications | 90% |
| `tests/tasks/test_alert_tasks.py` | Celery task uses AlertService, suppression tracking | 85% |
| `tests/observability/test_metrics.py` | All 11 new metrics recorded correctly | 95% |
| `tests/api/test_metrics_dashboard.py` | Prometheus query path, fallback, feature flag | 80% |
| `tests/evaluation/test_metrics.py` | answer_correctness metric recording | 80% |
| `tests/core/test_cache.py` | Cache hit/miss metrics | 80% |
| `tests/safety/test_moderator.py` | Safety block metrics | 80% |
| `tests/context/test_pii_filter.py` | PII detection metrics | 80% |
| `tests/core/test_limiter.py` | Rate limit metrics | 80% |

### CI Requirements
- All new tests pass: `uv run pytest`
- Coverage gate: `uv run pytest --cov=app --cov-fail-under=75`
- Lint: `uv run ruff check app tests --fix`
- Types: `uv run ty check --error-on-warning app tests`

---

## 8. Questions for User Decision

### Q1: Missing 6th Rule Implementation
AlertRuleEngine has 6 rules; AlertService has 5. The missing rule (`low_confidence`) queries `confidence_score` which is not currently aggregated in `alert_tasks._get_metric_value()`. 

**Options**:
- **A**: Add `confidence_score` aggregation to `_get_metric_value()` (adds ~15 lines, clean)
- **B**: Omit this rule from migration (if confidence is tracked elsewhere)
- **C**: Use a different metric source for confidence

**Recommendation**: Option A

### Q2: Prometheus Target IP Hardcoding
`prometheus/prometheus.yml` has hardcoded `192.168.31.59:8000`. Should this be templated?

**Options**:
- **A**: Use environment variable substitution (e.g., `${APP_HOST:-localhost}:8000`)
- **B**: Keep hardcoded, document in setup guide
- **C**: Use Docker service discovery

**Recommendation**: Option A + document

### Q3: `tokens_total` vs `token_usage_total`
Both metrics exist. `token_usage_total` has `agent` label; `tokens_total` is aggregate.

**Options**:
- **A**: Keep both (different purposes)
- **B**: Remove `tokens_total`, update dashboard to use `sum(token_usage_total)`
- **C**: Rename existing metric (breaking change)

**Recommendation**: Option A (no breaking changes in Phase 1)

### Q4: Agent Latency Instrumentation Point
`agent_latency_seconds` needs to measure agent execution time. The best insertion point is in the graph execution layer, not token_tracker.

**Options**:
- **A**: Instrument in `app/graph/nodes.py` where agents are invoked
- **B**: Instrument in `app/observability/token_tracker.py` (less accurate)
- **C**: Add decorator to agent classes

**Recommendation**: Option A for accuracy

### Q5: Feature Flag Storage
Should feature flags be in `app/core/config.py` (static) or DB-driven (dynamic)?

**Options**:
- **A**: Static in config.py (simpler, restart required)
- **B**: DB-driven with admin UI (complex, no restart)
- **C**: Hybrid: config.py defaults + DB override

**Recommendation**: Option A for Phase 1 (YAGNI - flags will stabilize quickly)

---

## 9. Execution Checklist

### Pre-Execution
- [ ] User confirms Q1-Q5 decisions
- [ ] Verify `grafana/dashboards/` JSON files expect these exact metric names
- [ ] Check if `app/graph/nodes.py` exists and is the right instrumentation point
- [ ] Confirm test environment has Redis available for sync suppression tests

### Wave 1 Execution
- [ ] Task 1.1: Remove deprecated files, migrate 6th rule
- [ ] Task 1.2: Create alertmanager config, update docker-compose
- [ ] Task 1.4: Define 11 metrics, instrument all points
- [ ] Task 1.6: Add Loki + Promtail to monitoring stack

### Wave 2 Execution
- [ ] Task 1.3: Connect Celery to AlertService notifications
- [ ] Task 1.5: Add Prometheus query capability with feature flag

### Post-Execution
- [ ] Integration test: Full alert flow (metric → rule → notification)
- [ ] Integration test: Dashboard metrics consistency (Prometheus vs PostgreSQL)
- [ ] Load test: Prometheus query performance under load
- [ ] Verify Grafana dashboards show data for all panels
- [ ] Run full test suite: `uv run pytest --cov=app --cov-fail-under=75`

---

## 10. Success Criteria (Phase 1 Complete)

- [ ] `alerting.py` and `alert_rules.py` removed; zero import errors
- [ ] Alertmanager routes Prometheus alerts to configured channels
- [ ] Celery tasks send real notifications for P0/P1 alerts
- [ ] All 11 missing metrics visible on `/metrics` endpoint
- [ ] Grafana dashboards show data in all panels
- [ ] Admin API can query Prometheus (behind feature flag)
- [ ] Loki aggregates application logs, queryable in Grafana
- [ ] Test coverage ≥ 75%
- [ ] All CI checks pass (ruff, ty, pytest)

---

## Appendix: File Inventory

### Files to Create (8)
1. `alertmanager/alertmanager.yml`
2. `loki/loki-config.yml`
3. `promtail/promtail-config.yml`
4. `grafana/provisioning/datasources/loki.yml`
5. `app/services/prometheus_client.py`
6. `tests/test_alert_service_sync.py`
7. `tests/observability/test_new_metrics.py`
8. `tests/api/test_prometheus_dashboard.py`

### Files to Modify (10)
1. `app/services/alert_service.py` - Add sync methods
2. `app/tasks/alert_tasks.py` - Use AlertService
3. `app/observability/metrics.py` - Add 11 metrics
4. `app/evaluation/metrics.py` - Instrument answer_correctness
5. `app/observability/token_tracker.py` - Instrument token metrics
6. `app/core/cache.py` - Instrument cache metrics
7. `app/safety/output_moderator.py` - Instrument safety metrics
8. `app/context/pii_filter.py` - Instrument PII metrics
9. `app/core/limiter.py` - Instrument rate limit metrics
10. `app/api/v1/admin/metrics_dashboard.py` - Add Prometheus query

### Files to Delete (2)
1. `app/observability/alerting.py`
2. `app/observability/alert_rules.py`

### Config Files to Modify (4)
1. `prometheus/prometheus.yml` - Add alertmanager target
2. `docker-compose.monitoring.yml` - Add alertmanager, Loki, Promtail
3. `app/core/config.py` - Add feature flags
4. `app/observability/AGENTS.md` - Remove deleted file references
