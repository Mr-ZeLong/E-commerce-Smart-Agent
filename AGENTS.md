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
3. For architecture details, read [`architecture.md`](architecture.md).
4. For project overview and screenshots, read [`README.md`](README.md).

## Context-Aware Loading

Use the right `AGENTS.md` for the area you're working in:

- **Agent implementations** (`app/agents/**`) → [`app/agents/AGENTS.md`](app/agents/AGENTS.md)
- **LangGraph workflow** (`app/graph/**`) → [`app/graph/AGENTS.md`](app/graph/AGENTS.md)
- **Intent recognition** (`app/intent/**`) → [`app/intent/AGENTS.md`](app/intent/AGENTS.md)
- **Memory system** (`app/memory/**`) → [`app/memory/AGENTS.md`](app/memory/AGENTS.md)
- **Tests** (`tests/**`) → [`tests/AGENTS.md`](tests/AGENTS.md)
- **Admin frontend** (`frontend/src/apps/admin/**`) → [`frontend/src/apps/admin/AGENTS.md`](frontend/src/apps/admin/AGENTS.md)
- **Customer frontend** (`frontend/src/apps/customer/**`) → [`frontend/src/apps/customer/AGENTS.md`](frontend/src/apps/customer/AGENTS.md)

For any other area, this root file applies.

## Repo Map

- `app/`: FastAPI backend, LangGraph workflow, agents, tools, services, observability, evaluation.
- `frontend/`: React 19 + TypeScript frontend (Vite, Tailwind CSS, shadcn/ui).
- `tests/`: Backend test suite (pytest + pytest-asyncio), organized by module (`tests/intent/`, `tests/graph/`, `tests/memory/`, `tests/evaluation/`, etc.).
- `scripts/`: Seed data, ETL, and utility scripts.
- `migrations/`: Alembic database migrations.
- `data/`: Static seed data (policies, products).
- `docs/`: Project documentation.

## Quick Commands

### Setup & Run

```bash
# One-shot startup (infrastructure + backend + frontend build)
./start.sh

# Manual backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Manual Celery worker (run from repo root)
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo
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

# Frontend E2E
cd frontend && npm run test:e2e
```

## Repo-Wide Invariants

### 1. Async-First
All backend code is async. Use `AsyncSession`, `await llm.ainvoke(...)`, async FastAPI routes, and async database drivers.

### 2. Multi-Tenant Isolation
Every query involving orders, refunds, carts, or user memories must filter by the current `user_id`. Never return cross-user data.

### 3. No Hardcoded Secrets
Use `app.core.config.settings` for all configuration. Never read `os.environ` directly outside of `app/core/config.py`.

### 4. Type Safety
- Python: never suppress type errors with `typing.Any` casts or `# type: ignore`.
- Frontend: follow the existing TypeScript strict mode.

### 5. Testing Requirements
- Every bug fix must include a test that reproduces the issue.
- New features must have matching tests in the appropriate `tests/` directory.
- CI requires `pytest --cov=app --cov-fail-under=75`.

### 6. AGENTS.md Hygiene
When modifying code in a scoped directory, check whether the nearest `AGENTS.md` needs updating (new conventions, changed file mappings, new anti-patterns).

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
