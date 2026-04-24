# AGENTS.md - E-commerce Smart Agent

> **IMPORTANT**: `AGENTS.md` files are the source of truth for AI agent instructions. Always update the relevant `AGENTS.md` file when adding or modifying agent guidance. Do not add durable guidance to editor-specific rule files only.

## Maintenance Contract

- `AGENTS.md` is a living document.
- Keep this root file concise and router-like. Push narrow or conditional workflows into package-local `AGENTS.md` files.
- Update this file in the same PR when repo-level architecture, workflows, dependency boundaries, mandatory verification commands, or security processes materially change.
- For package-local material changes, update the nearest package `AGENTS.md` in the same PR.

## Read Order

1. Read this root `AGENTS.md` for repo-wide rules, commands, and routing.
2. Read the nearest nested `AGENTS.md` for the directory you are working in.
3. For architecture details, read [`docs/explanation/architecture/`](./docs/explanation/architecture/).
4. For project overview and screenshots, read [`README.md`](README.md).

## Context-Aware Loading

Use the right `AGENTS.md` for the area you're working in:

- **Agent implementations** (`@app/agents/**`) → [`app/agents/AGENTS.md`](app/agents/AGENTS.md)
- **LangGraph workflow** (`@app/graph/**`) → [`app/graph/AGENTS.md`](app/graph/AGENTS.md)
- **Intent recognition** (`@app/intent/**`) → [`app/intent/AGENTS.md`](app/intent/AGENTS.md)
- **Memory system** (`@app/memory/**`) → [`app/memory/AGENTS.md`](app/memory/AGENTS.md)
- **Tools** (`@app/tools/**`) → [`app/tools/AGENTS.md`](app/tools/AGENTS.md)
- **Retrieval** (`@app/retrieval/**`) → [`app/retrieval/AGENTS.md`](app/retrieval/AGENTS.md)
- **Evaluation** (`@app/evaluation/**`) → [`app/evaluation/AGENTS.md`](app/evaluation/AGENTS.md)
- **Observability** (`@app/observability/**`) → [`app/observability/AGENTS.md`](app/observability/AGENTS.md)
- **Tasks** (`@app/tasks/**`) → [`app/tasks/AGENTS.md`](app/tasks/AGENTS.md)
- **API layer** (`@app/api/**`) → [`app/api/AGENTS.md`](app/api/AGENTS.md)
- **Schemas** (`@app/schemas/**`) → [`app/schemas/AGENTS.md`](app/schemas/AGENTS.md)
- **Models** (`@app/models/**`) → [`app/models/AGENTS.md`](app/models/AGENTS.md)
- **Services** (`@app/services/**`) → [`app/services/AGENTS.md`](app/services/AGENTS.md)
- **Core** (`@app/core/**`) → [`app/core/AGENTS.md`](app/core/AGENTS.md)
- **Confidence** (`@app/confidence/**`) → [`app/confidence/AGENTS.md`](app/confidence/AGENTS.md)
- **Context** (`@app/context/**`) → [`app/context/AGENTS.md`](app/context/AGENTS.md)
- **Safety** (`@app/safety/**`) → [`app/safety/AGENTS.md`](app/safety/AGENTS.md)
- **WebSocket** (`@app/websocket/**`) → [`app/websocket/AGENTS.md`](app/websocket/AGENTS.md)
- **Utils** (`@app/utils/**`) → [`app/utils/AGENTS.md`](app/utils/AGENTS.md)
- **Tests** (`@tests/**`) → [`tests/AGENTS.md`](tests/AGENTS.md)
- **Admin frontend** (`@frontend/src/apps/admin/**`) → [`frontend/src/apps/admin/AGENTS.md`](frontend/src/apps/admin/AGENTS.md)
- **Customer frontend** (`@frontend/src/apps/customer/**`) → [`frontend/src/apps/customer/AGENTS.md`](frontend/src/apps/customer/AGENTS.md)

For any other area, this root file applies.

## Repo Map

- `@app/`: FastAPI backend, LangGraph workflow, agents, tools, services, observability, evaluation, memory, intent, retrieval, confidence, context, api, models, schemas, utils, websocket, tasks, core.
  - `@app/agents/`: Expert agent fleet (order, product, cart, payment, logistics, account, policy, complaint, supervisor, router, evaluator).
  - `@app/graph/`: LangGraph workflow compiler and runtime node layer.
    - `@app/graph/checkpointer.py` - OptimizedRedisCheckpoint with diff-based storage, compression, and TTL management.
    - `@app/graph/subgraphs.py` - Subgraph wrapper for agent state isolation.
  - `@app/intent/`: Intent recognition pipeline (classifier, multi-intent, safety, clarification, slot validation, topic switch).
    - `@app/intent/few_shot_loader.py` - Few-shot example loading for intent classification.
  - `@app/memory/`: Multi-tier memory system (structured PostgreSQL, vector Qdrant, fact extraction, summarization, compaction).
    - `@app/memory/structured_manager.py` - Structured memory manager for user profiles/preferences/facts.
  - `@app/tools/`: Tool layer for agents (product, cart, logistics, payment, account, complaint tools + registry).
  - `@app/tasks/`: Celery async tasks (memory, notifications, knowledge, refund, evaluation, continuous improvement, prompt effects, shadow testing).
    - `@app/tasks/alert_tasks.py` - Evaluate alert rules, check service health.
    - `@app/tasks/autoheal.py` - Self-healing orchestration module.
    - `@app/tasks/autoheal_tasks.py` - Restart stuck workers, clear expired Redis keys, check DB pool health.
    - `@app/tasks/checkpoint_tasks.py` - Cleanup old LangGraph checkpoints from Redis.
    - `@app/tasks/observability_tasks.py` - Post-chat async observability logging.
  - `@app/retrieval/`: Hybrid RAG retrieval (dense + sparse embeddings, reranker, query rewriter, Qdrant client).
    - `@app/retrieval/sparse_embedder.py` - Sparse embedding support (BM25).
  - `@app/evaluation/`: Offline evaluation framework (pipeline, adversarial, shadow, metrics, hallucination, containment).
  - `@app/observability/`: OpenTelemetry tracing, execution logging, latency tracking, Prometheus metrics.
    - `@app/observability/metrics.py` - Prometheus custom metrics (counters, histograms, gauges).
    - `@app/observability/prometheus_client.py` - Async Prometheus HTTP API client.
    - `@app/observability/token_tracker.py` - Per-user/per-agent cost monitoring.
  - `@app/confidence/`: Confidence signal calculation for response quality.
  - `@app/context/`: Context engineering (observation masking, token budget management).
    - `@app/context/pii_filter.py` - PII detection and filtering with regex patterns for credit cards, phone numbers, ID numbers, passports, email, SSN, bank accounts.
  - `@app/websocket/`: WebSocket connection manager for real-time chat.
  - `@app/schemas/`: Pydantic request/response schemas.
  - `@app/api/`: FastAPI routers (chat, auth, admin, websocket, status).
  - `@app/models/`: SQLModel/Pydantic data models (user, order, refund, memory, evaluation, experiment, etc.).
    - `@app/models/alert.py` - AlertRule, AlertEvent, AlertNotification models.
    - `@app/models/pii_audit.py` - PIIAuditLog model for GDPR compliance.
    - `@app/models/review.py` - ReviewTicket, ReviewerMetrics models.
    - `@app/models/token_usage.py` - TokenUsageLog, OptimizationSuggestion models.
  - `@app/services/`: Business logic services (auth, order, refund, admin, status, experiment, continuous improvement).
    - `@app/services/alert_service.py` - AlertService with email/webhook/PagerDuty/OpsGenie integrations, suppression, deduplication, SLA tracking.
    - `@app/services/online_eval.py` - OnlineEvalService for real-time evaluation from user feedback.
    - `@app/services/review_queue.py` - ReviewQueueService for human review tickets with SLA tracking.
  - `@app/core/`: Core configuration, security, database, Redis, LLM factory, tracing, logging (cross-cutting infrastructure).
    - `@app/core/cache.py` - CacheManager with 7 cache types + circuit breaker + Prometheus metrics.
    - `@app/core/structured_logging.py` - JsonFormatter with trace_id/span_id/correlation_id support.
  - `@app/core/utils.py`: Core cross-cutting utilities (`utc_now`, `build_thread_id`, `clamp_score`).
  - `@app/safety/`: Output content moderation system (4-layer pipeline: rule-based, regex, embedding similarity, LLM judge).
  - `@app/utils/`: Shared domain utility functions (order utilities, helpers).
- `@frontend/`: React 19 + TypeScript frontend (Vite, Tailwind CSS, shadcn/ui).
  - `@frontend/src/apps/admin/`: B端管理后台 (dashboard, knowledge base, agent config, feedback, analytics).
  - `@frontend/src/apps/customer/`: C端用户聊天界面 (SSE streaming chat).
- `@tests/`: Backend test suite (pytest + pytest-asyncio), organized by module.
- `scripts/`: Seed data, ETL, and utility scripts.
- `migrations/`: Alembic database migrations.
- `data/`: Static seed data (policies, products).
- `@docs/`: Project documentation.

## Quick Commands

### Setup & Run

```bash
# One-shot startup (infrastructure + backend + frontend build)
./start.sh

# Manual backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Scripted Celery worker (recommended for local development)
# Automatically waits for Redis, PostgreSQL, and Qdrant to be ready, then starts both worker and Beat scheduler
./start_worker.sh

# Manual Celery worker (use when dependencies are already running)
# Start worker + Beat scheduler directly without health checks; requires Redis/PostgreSQL/Qdrant to be up
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo --beat
```

### Database

```bash
# Run migrations
uv run alembic upgrade head

# Generate migration
uv run alembic revision --autogenerate -m "description"
```

### Testing & Quality

```bash
# Backend tests
uv run pytest
uv run pytest --cov=app --cov-fail-under=75

# Backend lint + format
uv run ruff check app tests --fix
uv run ruff format app tests
uv run ty check --error-on-warning app tests

# Frontend dev
cd frontend && npm run dev

# Frontend build
cd frontend && npm run build

# Frontend lint + format
cd frontend && npm run lint
cd frontend && npm run format

# Frontend E2E
cd frontend && npm run test:e2e
```

### Pre-commit

```bash
# Install hooks (run once)
pre-commit install

# Run all hooks manually
pre-commit run --all-files
```

## Repo-Wide Invariants

### 1. Async-First
All backend code is async. Use `AsyncSession`, `await llm.ainvoke(...)`, async FastAPI routes, and async database drivers.

### 2. Multi-Tenant Isolation
Every query involving orders, refunds, carts, or user memories must filter by the current `user_id`. Never return cross-user data.

### 3. No Hardcoded Secrets
Use `app.core.config.settings` for all configuration. Never read `os.environ` directly outside of `@app/core/config.py`.

### 4. Type Safety
- Python: never suppress type errors with `typing.Any` casts or `# type: ignore`, **except** when the diagnostic originates from a third-party package (e.g., missing stubs, incorrect annotations, or known compatibility issues like `ty` vs `pydantic-settings`). In that case, suppression is allowed only in the smallest scope and must include a comment explaining the reason and the package/version involved.
- Frontend: follow the existing TypeScript strict mode. Do not use `@ts-ignore` or implicit `any`.

### 5. Testing Requirements
- Every bug fix must include a test that reproduces the issue.
- New features must have matching tests in the appropriate `tests/` directory.
- CI requires `pytest --cov=app --cov-fail-under=75`.

### 6. AGENTS.md Hygiene
When modifying code in a scoped directory, check whether the nearest `AGENTS.md` needs updating (new conventions, changed file mappings, new anti-patterns).

## Code Style Guidelines

### Python
- **Docstrings**: Use Google-style docstrings for all public modules, classes, and functions.
- **Type hints**: Mandatory on all function signatures and class attributes. Never suppress type errors with `typing.Any` or `# type: ignore` except for third-party compatibility issues (see Invariant 4).
- **Error handling**: Never use bare `except:`. Always catch specific exceptions and propagate or log them.
- **Path handling**: Prefer `pathlib.Path` over `os.path` for file system operations.
- **Async**: All I/O-bound code must be `async`. No synchronous blocking calls in FastAPI routes or graph nodes.
- **Configuration**: All settings live in `@app/core/config.py`. Do not read `os.environ` directly outside this file.

### Frontend
- **TypeScript**: Follow strict mode. No implicit `any`.
- **Return types**: Explicit return types on all custom hooks and utility functions.
- **Components**: Prefer functional components with explicit prop interfaces.
- **Styling**: Use Tailwind CSS utilities. For dark mode, rely on `dark:` prefixes with `dark-mode: class` strategy.

## Testing Guidance

### Backend
- **Bug-fix TDD**: Every bug fix must start with a failing reproduction test.
- **Async tests**: All async tests must be decorated with `@pytest.mark.asyncio`.
- **Fixtures**: Reuse session-scoped fixtures from `@tests/conftest.py`. Use `@app/models/state.py` for `make_agent_state()` and `@tests/_llm.py` for LLM mocks.
- **Mock external I/O**: Mock LLM calls, database sessions, Redis, Qdrant, and email/SMS gateways in unit tests.
- **Coverage gate**: CI enforces `pytest --cov=app --cov-fail-under=75`. Do not let coverage drop below this threshold.
- **Test naming**: Use descriptive names: `test_<module>_<scenario>_<expected_outcome>`.

### Frontend
- **Unit tests**: Use Vitest for hooks and pure utilities.
- **E2E tests**: Use Playwright for critical user flows (login, chat, admin decisions, knowledge sync).
- **API mocking**: Mock API calls in unit tests; E2E tests hit the real backend or use MSW where appropriate.

## Formatting Rules

- **Python**: The linter (`ruff check`) ignores E501 because `ruff format` handles line-length=100 (wrapping) automatically. The formatter also enforces double quotes. Run `uv run ruff format app tests` and `uv run ruff check app tests --fix` before committing.
- **Python types**: Run `uv run ty check --error-on-warning app tests` and resolve all diagnostics.
- **Frontend**: `prettier` + `eslint` enforce consistent formatting. Run `cd frontend && npm run format && npm run lint` before committing.
- **Pre-commit**: The project uses `pre-commit` hooks (ruff, ty). Install them with `pre-commit install`.

## Comments Style

- **Docstrings**: Write docstrings in English for all public APIs. Start with a capital letter and end with a period.
- **Inline comments**: Use inline comments only for non-obvious logic or business-rule caveats. Keep them concise and in English.
- **No Chinese in code comments**: Project documentation and AGENTS.md can be bilingual; source-code comments should be in English to maintain consistency with upstream tooling and LLM context windows.
- **TODO/FIXME**: Prefix with `TODO(user):` or `FIXME(user):` and include a brief explanation and issue link if available.

## Committing Conventions

- **Conventional Commits**: All commits must follow the Conventional Commits specification:
  - `feat(scope): description`
  - `fix(scope): description`
  - `test(scope): description`
  - `docs(scope): description`
  - `refactor(scope): description`
  - `chore(scope): description`
  - `ci(scope): description`
- **Atomic commits**: Each commit should represent a single logical change. Do not mix unrelated features, fixes, and refactors in one commit.
- **AGENTS.md hygiene**: When a PR changes repo-wide architecture, workflows, dependency boundaries, or security processes, update the root `AGENTS.md` in the same PR. For package-local changes, update the nearest nested `AGENTS.md`.
- **Scope examples**: `feat(memory):`, `fix(agent):`, `test(graph):`, `docs(agents):`, `ci(frontend):`.

## Security Notes

- CORS origins are validated at startup; `*` with `allow_credentials=True` raises `RuntimeError`.
- Passwords are hashed with `bcrypt`; never store plaintext.
- Production must set `ENABLE_OPENAPI_DOCS=False` and rotate `SECRET_KEY`.
- OpenTelemetry OTLP endpoint is optional; when absent, tracing falls back to a no-op exporter.

## Environment Variables

Copy `.env.example` to `.env`. Key variables:
- `POSTGRES_*`, `REDIS_*`, `QDRANT_URL`
- `OPENAI_API_KEY` / `DASHSCOPE_API_KEY`
- `SECRET_KEY`, `CELERY_BROKER_URL`

See `.env.example` for the full list.
