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

- **Agent implementations** (`app/agents/**`) → [`app/agents/AGENTS.md`](app/agents/AGENTS.md)
- **LangGraph workflow** (`app/graph/**`) → [`app/graph/AGENTS.md`](app/graph/AGENTS.md)
- **Intent recognition** (`app/intent/**`) → [`app/intent/AGENTS.md`](app/intent/AGENTS.md)
- **Memory system** (`app/memory/**`) → [`app/memory/AGENTS.md`](app/memory/AGENTS.md)
- **Tests** (`tests/**`) → [`tests/AGENTS.md`](tests/AGENTS.md)
- **Admin frontend** (`frontend/src/apps/admin/**`) → [`frontend/src/apps/admin/AGENTS.md`](frontend/src/apps/admin/AGENTS.md)
- **Customer frontend** (`frontend/src/apps/customer/**`) → [`frontend/src/apps/customer/AGENTS.md`](frontend/src/apps/customer/AGENTS.md)

For any other area, this root file applies.

## Repo Map

- `app/`: FastAPI backend, LangGraph workflow, agents, tools, services, observability, evaluation, memory, intent, retrieval, confidence, context, api, models, schemas, utils, websocket, tasks, core.
- `frontend/`: React 19 + TypeScript frontend (Vite, Tailwind CSS, shadcn/ui).
- `tests/`: Backend test suite (pytest + pytest-asyncio), organized by module (`tests/intent/`, `tests/graph/`, `tests/memory/`, `tests/evaluation/`, `tests/context/`, `tests/observability/`, `tests/tasks/`, `tests/admin/`, `tests/services/`, etc.).
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

# Manual Celery worker (run from repo root, with Beat scheduler)
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
Use `app.core.config.settings` for all configuration. Never read `os.environ` directly outside of `app/core/config.py`.

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

- **Python**: `ruff` enforces line length 100, double quotes for strings, and 4-space indentation. Run `uv run ruff format app tests` before committing.
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
