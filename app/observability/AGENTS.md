# AGENTS.md - Observability

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the observability system.
- Update this file in the same PR when adding new telemetry, logging, or tracing components.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for observability-specific guidance.

## Overview

Observability layer providing OpenTelemetry tracing, execution logging, and latency tracking for the agent system. Enables debugging, performance monitoring, and audit trails.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Alert rules | `@app/observability/alert_rules.py` | Prometheus alert rule definitions with severity levels (P0/P1/P2) |
| Alerting | `@app/observability/alerting.py` | Alert management (AlertManager, AlertSeverity, alert lifecycle) |
| Execution logger | `@app/observability/execution_logger.py` | Graph execution logging with structured events |
| Latency tracker | `@app/observability/latency_tracker.py` | Per-node latency measurement and reporting |
| Prometheus metrics | `@app/observability/metrics.py` | Custom counters, histograms, and gauges for chat latency, token usage, intent accuracy, hallucination rate |
| OpenTelemetry setup | `@app/observability/otel_setup.py` | OTel tracer provider and exporter configuration |
| Token tracker | `@app/observability/token_tracker.py` | Per-user/per-agent cost monitoring with TokenTracker class |

## Commands

```bash
# Run observability module tests
uv run pytest tests/observability/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Observability-specific conventions:

- **Type hints**: All logging and tracing functions must be fully typed.
- **Structured logging**: Use structured JSON logs with correlation IDs for traceability.
- **Async-safe**: All observability hooks must be async-safe and non-blocking.

## Testing Patterns

- Mock OpenTelemetry tracer in tests to avoid external dependencies.
- Verify log structure (JSON schema, required fields) rather than exact content.
- Test latency tracking with synthetic delays (mock time).

## Conventions

- **Correlation IDs**: Propagate correlation IDs across all async boundaries for request tracing.
- **Span naming**: Use descriptive span names: `<module>.<function>`.
- **Sampling**: Configure trace sampling to avoid overwhelming the exporter in high-traffic scenarios.
- **PII redaction**: Redact sensitive fields (passwords, tokens) from logs and traces.

## Anti-Patterns

- **Logging in hot paths**: Avoid excessive logging in performance-critical code paths.
- **Blocking I/O in traces**: Never perform blocking I/O inside trace spans.
- **Unstructured text logs**: Use structured logging; avoid plain text logs that are hard to query.

## Related Files

- `@app/core/tracing.py` — Core tracing configuration and LangSmith integration.
- `@app/core/logging.py` — Logging utilities with correlation ID support.
- `@app/models/observability.py` — Data models for execution logs and supervisor decisions.
