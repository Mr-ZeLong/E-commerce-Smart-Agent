# AGENTS.md - Core

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for core infrastructure.
- Update this file in the same PR when adding new core utilities or changing infrastructure conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for core-specific guidance.

## Overview

Core infrastructure and cross-cutting concerns: configuration, security, database, Redis, LLM factory, tracing, logging, rate limiting, and email.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Configuration | `@app/core/config.py` | `Settings` with nested `ConfidenceSettings`; single source of truth for env vars. Uses `_create_settings()` factory to avoid top-level instantiation errors during static analysis |
| Security | `@app/core/security.py` | JWT token creation/validation, OAuth2 scheme, password hashing |
| Database | `@app/core/database.py` | AsyncSession makers, engine configuration |
| Redis | `@app/core/redis.py` | Redis client creation and connection pooling |
| LLM factory | `@app/core/llm_factory.py` | LLM instance creation (OpenAI, DashScope, etc.) |
| Tracing | `@app/core/tracing.py` | OpenTelemetry/LangSmith tracing configuration |
| Logging | `@app/core/logging.py` | Structured logging with correlation ID support |
| Email | `@app/core/email.py` | Email sending utilities |
| Rate limiting | `@app/core/limiter.py` | Request rate limiting configuration |
| Utilities | `@app/core/utils.py` | General utilities (`utc_now`, `build_thread_id`, `clamp_score`, etc.) |

## Commands

```bash
# Run core tests
uv run pytest tests/core/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Core-specific conventions:

- **Type hints**: All core utilities must be fully typed.
- **Async**: All I/O utilities (database, Redis, email) must be async.
- **Configuration**: All settings centralized in `config.py`; never read `os.environ` outside this file.
- **Cross-cutting**: Core modules are imported by many other modules; keep them stable and backward-compatible.

## Testing Patterns

- Mock external dependencies (database, Redis, email) in core tests.
- Test configuration loading with different environment variable sets.
- Verify security utilities (JWT, password hashing) with known inputs.

## Conventions

- **Settings singleton**: Access settings via `app.core.config.settings`.
- **Settings factory**: `_create_settings()` wraps `Settings()` instantiation to defer runtime env-file loading and avoid false positives during static analysis.
- **Type checker compatibility**: `config.py` suppresses `ty: ignore[missing-argument]` on `Settings()` because `ty` does not understand `pydantic-settings` env-file defaulting. This follows root `AGENTS.md` Invariant #4 (Type Safety): suppression is allowed for third-party compatibility issues when scoped to the smallest region and annotated with the reason.
- **Correlation IDs**: Use `logging.py` utilities to propagate correlation IDs across async boundaries.
- **Secret management**: Never log secrets or tokens; use `SecretStr` in Pydantic models.
- **LLM caching**: Cache LLM instances in `llm_factory.py` to avoid repeated initialization.

## Anti-Patterns

- **Direct env access**: Never read `os.environ` outside `config.py`.
- **Hardcoded secrets**: Never hardcode API keys, passwords, or tokens.
- **Synchronous I/O**: All core I/O must be async.

## Related Files

- `AGENTS.md` (root) — Defines repo-wide invariants that core modules enforce.
- `@app/api/v1/auth.py` — Uses `security.py` for authentication.
- `@app/celery_app.py` — Uses `config.py` for Celery configuration.
