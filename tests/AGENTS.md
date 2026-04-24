# AGENTS.md - Tests

> **IMPORTANT**: Read the root [`AGENTS.md`](../AGENTS.md) first for repo-wide rules, commands, and routing.

## Maintenance Contract

- `AGENTS.md` is a living document.
- Update this file in the same PR when test conventions, fixtures, or patterns materially change.
- Keep this file focused on test-specific guidance; do not duplicate root-level rules.

## Read Order

1. Read the root [`AGENTS.md`](../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for test-specific conventions and patterns.
3. For fixture details, read [`@tests/conftest.py`](conftest.py) and [`@tests/_llm.py`](_llm.py).

## Overview

Backend test suite using pytest + pytest-asyncio with a flat directory structure (not strictly mirroring `app/` subpackages).

## Key Files

| Task | File/Directory | Description |
|------|---------------|-------------|
| Global fixtures | `@tests/conftest.py` | `client`, `db_session`, `redis_client` |
| Test DB config | `@tests/_db_config.py` | Auto-prefixes DB names with `test_` |
| Agent mock | `@tests/_agents.py` | Agent mock factory and test helpers |
| LLM mock | `@tests/_llm.py` | LLM call mocks and response helpers |
| API tests | `@tests/test_auth_api.py`, `@tests/test_chat_api.py`, `@tests/test_admin_api.py` | Route-layer validation |
| Service tests | `@tests/test_order_service.py`, `@tests/test_refund_service.py`, `@tests/test_auth_service.py`, `@tests/test_status_service.py`, `@tests/test_admin_service.py` | Business logic validation |
| Module unit tests | `@tests/agents/`, `@tests/graph/`, `@tests/intent/`, `@tests/memory/`, `@tests/tools/`, `@tests/retrieval/`, `@tests/evaluation/`, `@tests/context/`, `@tests/observability/`, `@tests/core/`, `@tests/models/`, `@tests/performance/` | Agent/graph/intent/memory/RAG/evaluation/context/observability/core/model/performance tests |
| Graph module tests | `@tests/graph/test_checkpointer.py`, `@tests/graph/test_memory_integration.py`, `@tests/graph/test_parallel.py`, `@tests/graph/test_subgraphs.py`, `@tests/graph/test_workflow.py` | Checkpointer, memory integration, parallel dispatch, subgraph, and workflow compiler tests |
| Context module tests | `@tests/context/test_pii_filter.py`, `@tests/context/test_token_budget.py` | PII filtering and token budget tests |
| Core module tests | `@tests/core/test_cache.py`, `@tests/core/test_limiter.py`, `@tests/core/test_redis.py`, `@tests/core/test_structured_logging.py` | Cache manager, rate limiter, Redis pool, and structured logging tests |
| Observability module tests | `@tests/observability/test_latency_tracker.py`, `@tests/observability/test_metrics.py`, `@tests/observability/test_prometheus_client.py` | Latency tracker, metrics, and Prometheus client tests |
| Safety tests | `@tests/safety/test_output_moderator.py`, `@tests/safety/conftest.py` | 4-layer output moderation pipeline tests |
| Admin API tests | `@tests/admin/`, `@tests/api/admin/test_metrics_dashboard.py`, `@tests/api/admin/test_review_queue.py`, `@tests/api/admin/test_token_usage.py` | Admin endpoint tests including metrics, review queue, and token usage |
| Service tests | `@tests/services/test_continuous_improvement.py`, `@tests/services/test_alert_service.py` | Business service validation |
| Task tests | `@tests/tasks/`, `@tests/tasks/test_autoheal.py`, `@tests/tasks/test_continuous_improvement_tasks.py`, `@tests/tasks/test_shadow_tasks.py` | Celery task tests including autoheal, CI, and shadow testing |
| Integration tests | `@tests/integration/test_workflow_invoke.py` | LangGraph integration (including parallel multi-intent scenarios) |
| Security tests | `@tests/test_main_security.py`, `@tests/test_security.py`, `@tests/test_auth_rate_limit.py` | Security and rate limiting validation |
| WebSocket tests | `@tests/test_websocket.py`, `@tests/test_websocket_manager.py` | WebSocket connection tests |
| Confidence tests | `@tests/test_confidence_signals.py` | Confidence signal validation |
| User tests | `@tests/test_users.py` | User model and endpoint tests |
| Experiment tests | `@tests/test_experiment_assigner.py`, `@tests/test_experiment_service.py` | Experiment system tests |
| Evaluation tests | `@tests/test_evaluation_tasks.py`, `@tests/test_online_eval_service.py` | Evaluation system tests |
| Knowledge tests | `@tests/test_knowledge_tasks.py` | Knowledge base task tests |
| Notification tests | `@tests/test_notifications_tasks.py` | Notification task tests |
| Refund task tests | `@tests/test_refund_tasks.py` | Refund workflow task tests |
| Prompt effect tests | `@tests/test_prompt_effect_tasks.py` | Prompt effect tracking tests |
| Observability API tests | `@tests/test_observability_api.py` | Observability endpoint tests |
| Reranker mock | `@tests/_reranker.py` | Reranker mock helpers |
| Utility tests | `@tests/test_chat_utils.py`, `@tests/test_logging.py`, `@tests/test_email.py` | Utility function tests |

## Commands

```bash
# All backend tests
uv run pytest

# With coverage gate (CI requirement: --cov-fail-under=75)
uv run pytest --cov=app --cov-fail-under=75

# By module
uv run pytest tests/agents/
uv run pytest tests/graph/
uv run pytest tests/intent/
uv run pytest tests/memory/
uv run pytest tests/evaluation/
uv run pytest tests/context/
uv run pytest tests/observability/
uv run pytest tests/tasks/
uv run pytest tests/admin/
uv run pytest tests/services/
uv run pytest tests/safety/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Test-specific conventions:

- **Descriptive naming**: Use `test_<module>_<scenario>_<expected_outcome>` for all test functions.
- **Fixture reuse**: Prefer session-scoped fixtures from `@tests/conftest.py` over recreating setup per test.
- **Minimal mocks**: Use helper functions in `@tests/_llm.py` and `@tests/_agents.py` to construct mocks; avoid hardcoding large JSON blobs in tests.
- **No `time.sleep`**: Never use `time.sleep` to wait for async results. Use `asyncio.wait_for` or proper mocking instead.

## Testing Patterns

- **Bug-fix TDD**: Every bug fix must start with a failing reproduction test. Confirm the test fails before applying the fix.
- **Async tests**: All async tests must be decorated with `@pytest.mark.asyncio`.
- **State factory**: Use `make_agent_state()` from `@app/models/state.py` to construct agent state; avoid assembling state objects inline across multiple tests.
- **LLM mocking**: Use helpers in `@tests/_llm.py` to construct mock responses. Prefer real LLM tests for components that directly invoke LLMs; use mocks for error handling, edge cases, batch operations, and components that do not directly call LLMs.
- **External service isolation**: Unit tests should not call database, Redis, Qdrant, or SMS gateways directly. Integration tests may access the test DB in controlled environments.
- **Real LLM tests**: Mark tests that require a real LLM with `@pytest.mark.requires_llm`. These tests skip automatically when `OPENAI_API_KEY` or `DASHSCOPE_API_KEY` is not configured. Use the `real_llm` fixture from `@tests/conftest.py` for real LLM instances.
- **Coverage gate**: CI enforces `pytest --cov=app --cov-fail-under=75`. Do not lower the threshold; add tests for uncovered code instead.

## Conventions

- **Flat structure**: Tests do not strictly mirror `app/` subpackage paths.
- **Naming**: Descriptive test names that convey scenario and expected outcome.
- **Fixture reuse**: Use session-scoped fixtures from `@tests/conftest.py` to avoid repeated DB connection overhead.

## Anti-Patterns

- **Monolithic test files**: Large test files with many test methods should be split by concern (e.g., split by feature or test type rather than accumulating in a single file).
- **Repeated mock state blocks**: Extract repeated mock state construction into fixtures or helper functions in `@tests/_agents.py`.
- **`time.sleep` in tests**: Never use `time.sleep` for async results; use proper async waiting or mocking.
- **Skipping coverage**: Do not skip coverage checks locally; when uncovered code is found, add tests rather than lowering thresholds.

## Related Files

- `frontend/` — Frontend tests run independently (Vitest + Playwright) and are not included in backend pytest coverage statistics.
