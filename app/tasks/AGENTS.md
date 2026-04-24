# AGENTS.md - Tasks

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for Celery async tasks.
- Update this file in the same PR when adding new tasks or changing task conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for task-specific guidance.

## Overview

Celery async task layer for background processing. Tasks are triggered by graph nodes and services to perform non-blocking operations like fact extraction, notifications, knowledge sync, and evaluation.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Alert evaluation | `@app/tasks/alert_tasks.py` | Evaluate alert rules and check service health |
| Autoheal orchestration | `@app/tasks/autoheal.py` | Self-healing orchestration module for system health |
| Autoheal tasks | `@app/tasks/autoheal_tasks.py` | Restart stuck workers, clear expired Redis keys, check DB pool health |
| Checkpoint cleanup | `@app/tasks/checkpoint_tasks.py` | Cleanup old LangGraph checkpoints from Redis (max 100 per thread) |
| Memory tasks | `@app/tasks/memory_tasks.py` | Async fact extraction and vector pruning |
| Notifications | `@app/tasks/notifications.py` | Email/SMS notification sending |
| Observability logging | `@app/tasks/observability_tasks.py` | Post-chat async observability logging to keep SSE critical path fast |
| Knowledge tasks | `@app/tasks/knowledge_tasks.py` | Knowledge base sync and embedding |
| Refund tasks | `@app/tasks/refund_tasks.py` | Refund processing workflows |
| Evaluation tasks | `@app/tasks/evaluation_tasks.py` | Async evaluation runs |
| Continuous improvement | `@app/tasks/continuous_improvement_tasks.py` | CI pipeline tasks |
| Prompt effect tracking | `@app/tasks/prompt_effect_tasks.py` | Prompt A/B effect measurement |
| Shadow testing | `@app/tasks/shadow_tasks.py` | Shadow mode testing tasks |
| Tracing setup | `@app/tasks/tracing_setup.py` | Celery LangSmith tracing configuration |

## Commands

```bash
# Run task module tests
uv run pytest tests/tasks/

# Start Celery worker (recommended: auto-waits for dependencies)
./start_worker.sh

# Manual start (when dependencies are already running)
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo --beat
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Task-specific conventions:

- **Type hints**: All Celery task functions must have complete type annotations.
- **Docstrings**: Google-style docstrings for all tasks explaining purpose and parameters.
- **Error handling**: Tasks must handle failures gracefully and retry with exponential backoff.
- **Idempotency**: Design tasks to be idempotent; safe to retry without side effects.

## Testing Patterns

- Mock Celery `apply_async` and `delay` in unit tests.
- Test task logic independently of Celery infrastructure.
- Verify retry behavior with mocked failures.
- Test task chaining and dependency resolution.

## Conventions

- **Async triggers**: Graph nodes trigger tasks via `apply_async` to avoid blocking SSE responses.
- **Task naming**: Use descriptive task names: `<module>.<task_name>`.
- **Result storage**: Store task results in Redis or database for retrieval by frontend polling.
- **Max retries**: Set reasonable max retries (3-5) with exponential backoff (2^n seconds).

## Anti-Patterns

- **Synchronous LLM calls in tasks**: While tasks run in background, avoid blocking the worker with long LLM calls; use timeouts.
- **Database locks in tasks**: Avoid long-running transactions that hold database locks.
- **Missing error handling**: Always handle exceptions in tasks to prevent worker crashes.

## Related Files

- `@app/celery_app.py` — Celery application configuration.
- `@app/memory/extractor.py` — Fact extraction triggered by memory tasks.
- `@app/memory/summarizer.py` — Session summarization triggered from graph nodes.
