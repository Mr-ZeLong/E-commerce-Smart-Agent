# SLO/SLI Reference for E-commerce Smart Agent

> **Status**: Phase 3.2 — Core SLOs defined, recording rules deployed, Grafana dashboard available.

## Overview

This document defines the **Service Level Objectives (SLOs)** and **Service Level Indicators (SLIs)** for the E-commerce Smart Agent. SLOs express the desired reliability target; SLIs are the concrete metrics that measure whether the target is met.

All SLIs are derived from existing Prometheus metrics in `app/observability/metrics.py`. Recording rules in `prometheus/recording_rules.yml` pre-compute SLI values over the evaluation window to keep dashboard queries fast and consistent.

---

## SLO Summary Table

| SLO | Target | Window | Recording Rule Prefix |
|-----|--------|--------|----------------------|
| Availability | 99.9 % | 30 days | `slo:availability:*` |
| Latency | 95 % < 2 s | 7 days | `slo:latency:*` |
| Accuracy | 98 % intent accuracy | 7 days | `slo:accuracy:*` |
| Cost | $0.05 / request avg | 30 days | `slo:cost:*` |
| Security | 99.99 % PII blocked | 30 days | `slo:security:*` |

---

## 1. Availability SLO

**Objective**: The service is available 99.9 % of the time over a rolling 30-day window.

**Error budget**: 0.1 % downtime ≈ 43 minutes per month.

### SLIs

| SLI | Description | PromQL Expression (recording rule) |
|-----|-------------|------------------------------------|
| **SLI 1** — Service availability | Ratio of time the `/metrics` endpoint is reachable. | `avg_over_time(up{job="ecommerce-agent"}[30d])` |
| **SLI 2** — Error rate | Proportion of chat requests that result in an error. | `sum(rate(chat_errors_total[30d])) / sum(rate(chat_requests_total[30d]))` |

### Recording Rules

- `slo:availability:ratio_30d` — Overall availability ratio.
- Derived from `up{job="ecommerce-agent"}` and `chat_errors_total / chat_requests_total`.

---

## 2. Latency SLO

**Objective**: 95 % of chat requests complete in less than 2 seconds over a rolling 7-day window.

**Error budget**: 5 % of requests may exceed 2 s.

### SLIs

| SLI | Description | PromQL Expression (recording rule) |
|-----|-------------|------------------------------------|
| **SLI 1** — P95 latency | 95th percentile of chat latency. | `histogram_quantile(0.95, sum(rate(chat_latency_seconds_bucket[7d])) by (le))` |
| **SLI 2** — P99 latency | 99th percentile of chat latency (guardrail). | `histogram_quantile(0.99, sum(rate(chat_latency_seconds_bucket[7d])) by (le))` |

### Recording Rules

- `slo:latency:p95_7d` — P95 chat latency over 7 days.
- `slo:latency:p99_7d` — P99 chat latency over 7 days.

---

## 3. Accuracy SLO

**Objective**: Intent classification accuracy is at least 98 % over a rolling 7-day window.

**Error budget**: 2 % of classifications may be incorrect.

### SLIs

| SLI | Description | PromQL Expression (recording rule) |
|-----|-------------|------------------------------------|
| **SLI 1** — Intent accuracy | Average intent classification accuracy. | `avg(intent_accuracy) or vector(1)` |
| **SLI 2** — RAG precision | Precision of retrieval-augmented generation. | `rag_precision` |
| **SLI 3** — Hallucination rate | Rate of hallucinated responses (must stay low). | `hallucination_rate` |

### Recording Rules

- `slo:accuracy:intent_7d` — Intent accuracy over 7 days (gauge-based, `avg_over_time`).
- `slo:accuracy:rag_7d` — RAG precision over 7 days.
- `slo:accuracy:hallucination_7d` — Hallucination rate over 7 days.

---

## 4. Cost SLO

**Objective**: Average cost per request does not exceed $0.05 over a rolling 30-day window.

**Error budget**: Cost per request may exceed $0.05 for a small fraction of traffic, provided the 30-day average stays within budget.

### SLIs

| SLI | Description | PromQL Expression (recording rule) |
|-----|-------------|------------------------------------|
| **SLI 1** — Tokens per request | Average tokens consumed per chat request. | `sum(rate(tokens_total[30d])) / sum(rate(chat_requests_total[30d]))` |
| **SLI 2** — Cache hit ratio | Ratio of cache hits to total cache lookups. | `sum(rate(cache_hits_total[30d])) / (sum(rate(cache_hits_total[30d])) + sum(rate(cache_misses_total[30d])))` |

> **Note**: The tokens-per-request SLI is converted to an estimated dollar cost using a per-token rate ($0.00001 per token as a conservative estimate). The recording rule stores tokens/request; the Grafana panel multiplies by the per-token rate to display dollars.

### Recording Rules

- `slo:cost:token_per_request_30d` — Tokens per request over 30 days.
- `slo:cost:cache_hit_ratio_30d` — Cache hit ratio over 30 days.

---

## 5. Security SLO

**Objective**: 99.99 % of PII is detected and blocked over a rolling 30-day window.

**Error budget**: 0.01 % of PII may go undetected or unblocked.

### SLIs

| SLI | Description | PromQL Expression (recording rule) |
|-----|-------------|------------------------------------|
| **SLI 1** — PII detection ratio | Proportion of PII events that were detected. | `sum(rate(pii_detections_total[30d])) / (sum(rate(pii_detections_total[30d])) + sum(rate(pii_breaches_total[30d])))` |
| **SLI 2** — Injection block ratio | Proportion of injection attempts that were blocked. | `sum(rate(injection_attempts_total[30d])) / (sum(rate(injection_attempts_total[30d])) + sum(rate(injection_bypassed_total[30d])))` |
| **SLI 3** — Safety block ratio | Proportion of safety checks that resulted in a block. | `sum(rate(safety_blocks_total[30d])) / sum(rate(safety_checks_total[30d]))` |

> **Note**: `pii_breaches_total`, `injection_bypassed_total`, and `safety_checks_total` are metrics that must be emitted by the application security layer. If they are absent, the recording rules return `NaN` and the dashboard shows "No Data". The rules are defined so they work immediately once those metrics are added.

### Recording Rules

- `slo:security:pii_detection_ratio_30d` — PII detection ratio over 30 days.
- `slo:security:injection_block_ratio_30d` — Injection block ratio over 30 days.
- `slo:security:safety_block_ratio_30d` — Safety block ratio over 30 days.

---

## Error Budget and Burn Rate

For each SLO, the **error budget** is defined as:

```text
error_budget_remaining = 1 - (actual / target)        # for ratio SLIs
error_budget_remaining = (target - actual) / target   # for threshold SLIs
```

The **burn rate** tells us how fast the error budget is being consumed:

```text
burn_rate = (1 - actual/target) / (elapsed_time / window)
```

A burn rate > 1 means the error budget will be exhausted before the window ends.

### Burn Rate Alerting Thresholds (for future alert rules)

| Burn Rate | Meaning | Action |
|-----------|---------|--------|
| > 1 | Budget will be exhausted | Page on-call |
| > 2 | Budget consumed 2× faster | Escalate |
| > 14.4 | 2 % budget in 1 hour | Immediate response |

---

## Dashboard

The Grafana SLO dashboard (`grafana/dashboards/slo.json`) contains panels for:

1. **SLO Current Value vs Target** — Gauges showing where each SLI stands relative to its target.
2. **Error Budget Remaining** — Bar gauges showing how much error budget is left.
3. **Burn Rate** — Time-series showing the rate of error budget consumption.
4. **30-Day Trend** — Graphs showing each SLI over the last 30 days.
5. **SLO Breach Alerts** — Alert list panel highlighting any SLO currently in breach.

---

## Recording Rule Reference

| Rule Name | SLI | Window |
|-----------|-----|--------|
| `slo:availability:ratio_30d` | Availability | 30d |
| `slo:latency:p95_7d` | P95 latency | 7d |
| `slo:latency:p99_7d` | P99 latency | 7d |
| `slo:accuracy:intent_7d` | Intent accuracy | 7d |
| `slo:accuracy:rag_7d` | RAG precision | 7d |
| `slo:accuracy:hallucination_7d` | Hallucination rate | 7d |
| `slo:cost:token_per_request_30d` | Tokens/request | 30d |
| `slo:cost:cache_hit_ratio_30d` | Cache hit ratio | 30d |
| `slo:security:pii_detection_ratio_30d` | PII detection | 30d |
| `slo:security:injection_block_ratio_30d` | Injection block | 30d |
| `slo:security:safety_block_ratio_30d` | Safety block | 30d |

---

## Related Files

- `prometheus/recording_rules.yml` — Prometheus recording rule definitions.
- `prometheus/prometheus.yml` — Prometheus configuration (references recording rules).
- `grafana/dashboards/slo.json` — Grafana SLO dashboard.
- `app/observability/metrics.py` — Source of all underlying metrics.
- `tests/observability/test_slo_queries.py` — Unit tests for recording rules.
