# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

E-commerce Smart Agent is a full-stack AI customer service system. Backend: FastAPI + LangGraph multi-agent orchestration. Frontend: React 19 + TypeScript + Vite. Python 3.12+ required. Package manager: `uv` (Python), `npm` (frontend).

## Common Commands

### Setup & Run

```bash
# One-shot startup (infra + backend + frontend build)
./start.sh

# Manual backend (requires Redis, PostgreSQL, Qdrant running)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery worker + Beat scheduler (recommended: auto-waits for deps)
./start_worker.sh

# Manual Celery (deps must already be up)
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo --beat
```

### Dependencies

```bash
# Python (uses uv.lock)
uv sync

# Frontend
cd frontend && npm install
```

### Database

```bash
# Run migrations
uv run alembic upgrade head

# Generate migration
uv run alembic revision --autogenerate -m "description"
```

### Testing

```bash
# Backend — all tests
uv run pytest

# Backend — with coverage gate (CI requirement: 75%)
uv run pytest --cov=app --cov-fail-under=75

# Run a single test file
uv run pytest tests/test_chat_api.py

# Run a single test
uv run pytest tests/test_chat_api.py::test_chat_endpoint_returns_200

# Frontend unit tests
cd frontend && npm run test

# Frontend E2E
cd frontend && npm run test:e2e
```

### Lint & Format

```bash
# Python
uv run ruff check app tests --fix
uv run ruff format app tests
uv run ty check --error-on-warning app tests

# Frontend
cd frontend && npm run lint && npm run format

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Monitoring Stack

```bash
# Start observability stack (Prometheus, Grafana, Loki, Tempo, Alertmanager, Mimir, OTel Collector)
docker compose -f docker-compose.monitoring.yml up -d
```

## Architecture

### Application Entry Points

- **`app/main.py`** — FastAPI app with lifespan manager. Bootstraps all agents, tools, retriever, memory managers, graph compiler, and Redis broadcast bridge. Serves built frontend SPAs at `/app` (customer) and `/admin` (admin).
- **`app/celery_app.py`** — Celery configuration with scheduled tasks (auto-healing, checkpoint cleanup, alert evaluation, shadow tests, adversarial evaluation).
- **`frontend/src/apps/customer/`** — C端聊天界面 SPA.
- **`frontend/src/apps/admin/`** — B端管理后台 SPA.

### Request Flow

1. Chat request hits `POST /api/v1/chat` (`app/api/v1/chat.py`)
2. `IntentRecognitionService` classifies intent (`app/intent/`)
3. `IntentRouterAgent` determines routing (`app/agents/router.py`)
4. `SupervisorAgent` orchestrates agent execution (`app/agents/supervisor.py`)
5. LangGraph state machine executes nodes (`app/graph/workflow.py`)
6. Agent executes tools via `ToolRegistry` (`app/tools/registry.py`)
7. `ConfidenceEvaluator` scores response quality (`app/agents/evaluator.py`)
8. 4-layer safety pipeline filters output (`app/safety/`)
9. Response streamed back via SSE or WebSocket

### Agent Fleet

All agents live in `app/agents/`:
- `router.py` — routes user intent to the correct agent
- `supervisor.py` — orchestrates parallel/serial agent execution via LangGraph
- `evaluator.py` — confidence scoring for response quality
- `order.py`, `product.py`, `cart.py`, `payment.py`, `logistics.py`, `account.py`, `policy.py`, `complaint.py` — domain-specific agents

Agents use `ToolRegistry` (registered in `app.main:lifespan`) to access tools defined in `app/tools/`.

### Memory System

Two-tier architecture:
- **Structured memory** (`app/memory/structured_manager.py`) — PostgreSQL stores user profiles, preferences, facts. Managed by `StructuredMemoryManager`.
- **Vector memory** (`app/memory/vector_manager.py`) — Qdrant stores conversation embeddings. Managed by `VectorMemoryManager`.
- LangGraph checkpoints use `OptimizedRedisCheckpoint` (`app/graph/checkpointer.py`) with diff-based storage and TTL.

### Retrieval (RAG)

`app/retrieval/` provides hybrid dense + sparse retrieval:
- Dense embeddings via fastembed
- Sparse embeddings via BM25 (`app/retrieval/sparse_embedder.py`)
- Query rewriter and reranker integrated
- Qdrant as vector store

### Observability

- **Tracing**: OpenTelemetry (`app/observability/otel_setup.py`) — exports to Tempo via OTLP. Every request gets `X-Correlation-ID` and `X-Trace-ID` headers.
- **Metrics**: Prometheus custom metrics (`app/observability/metrics.py`), exposed at `/metrics`. Async Prometheus HTTP client for querying.
- **Logging**: Structured JSON logging with trace/span IDs (`app/core/structured_logging.py`).
- **Token tracking**: Per-user/per-agent cost monitoring (`app/observability/token_tracker.py`).

### Celery Tasks

Located in `app/tasks/`. Key task modules:
- `autoheal_tasks.py` — restart stuck workers, clear expired Redis keys, check DB pool
- `checkpoint_tasks.py` — cleanup old LangGraph checkpoints
- `alert_tasks.py` — evaluate alert rules, check service health
- `observability_tasks.py` — post-chat async logging

Scheduled via `beat_schedule` in `app/celery_app.py`.

### Graph Workflow

- `app/graph/workflow.py` — compiles the LangGraph state machine
- `app/graph/checkpointer.py` — Redis-backed checkpointing with compression
- `app/graph/subgraphs.py` — subgraph wrapper for agent state isolation
- State model: `app/models/state.py` (`AgentState`)

## Key Conventions

- **Async-first**: All I/O-bound backend code is async. Use `AsyncSession`, `await llm.ainvoke(...)`, async FastAPI routes.
- **Multi-tenant isolation**: Every query involving orders, refunds, carts, or memories must filter by `user_id`. Never return cross-user data.
- **Settings centralization**: All config lives in `app.core.config.settings`. Never read `os.environ` directly outside `app/core/config.py`.
- **Type safety**: Never suppress type errors with `typing.Any` or `# type: ignore` except for third-party package compatibility. Frontend uses strict TypeScript — no `@ts-ignore`.
- **Conventional Commits**: `feat(scope):`, `fix(scope):`, `test(scope):`, etc. Scope examples: `memory`, `agent`, `graph`, `frontend`.
- **Docstrings**: Google-style, English only. Inline comments in English only.

## Testing

- Bug fixes must include a reproduction test.
- Async tests need `@pytest.mark.asyncio`.
- Reuse fixtures from `tests/conftest.py`: `client`, `db_session`, `redis_client`, `qdrant_client`, `deterministic_llm`.
- Mock LLM calls in unit tests — use `tests/_llm.py` for deterministic LLM mocks.
- `tests/_db_config.py` patches DB config for test isolation.

## Environment

Copy `.env.example` to `.env`. Key services and default ports:
- FastAPI API: `localhost:8000`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Qdrant: `localhost:6333`
- Prometheus: `localhost:9090`
- Grafana: `localhost:3000`
- Tempo: `localhost:3200`

## Additional Guidance

For module-specific rules, read the nearest `AGENTS.md`:
- `app/agents/AGENTS.md` — agent implementations
- `app/graph/AGENTS.md` — LangGraph workflow
- `app/memory/AGENTS.md` — memory system
- `tests/AGENTS.md` — testing conventions
- `frontend/src/apps/admin/AGENTS.md` — admin frontend
- `frontend/src/apps/customer/AGENTS.md` — customer frontend

The root `AGENTS.md` contains the full repo map, code style guidelines, and security notes.
