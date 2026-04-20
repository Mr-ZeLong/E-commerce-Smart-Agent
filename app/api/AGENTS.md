# AGENTS.md - API

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the API layer.
- Update this file in the same PR when adding new routes, endpoints, or changing API conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for API-specific guidance.

## Overview

FastAPI router layer defining RESTful and WebSocket endpoints for the agent system. Organized under `app/api/v1/` with admin subroutes.

Note: WebSocket routes (`app/api/v1/websocket.py`) are the FastAPI entrypoints that delegate connection management to `app/websocket/manager.py`.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Chat API | `app/api/v1/chat.py` | POST /chat (SSE streaming), POST /feedback |
| Auth API | `app/api/v1/auth.py` | POST /login, POST /register, GET /me |
| WebSocket API | `app/api/v1/websocket.py` | WS /ws/{thread_id}, WS /ws/admin/{admin_id} |
| Status API | `app/api/v1/status.py` | Thread status endpoints |
| API schemas | `app/api/v1/schemas.py` | Pydantic request/response schemas (legacy location) |
| Chat utilities | `app/api/v1/chat_utils.py` | SSE metadata message utilities (v4.1 confidence metadata) |
| Admin agent config | `app/api/v1/admin/agent_config.py` | Agent configuration admin endpoints |
| Admin complaints | `app/api/v1/admin/complaints.py` | Complaint management endpoints |
| Admin analytics | `app/api/v1/admin/analytics.py` | Analytics data endpoints |
| Admin feedback | `app/api/v1/admin/feedback.py` | Feedback management endpoints |
| Admin experiments | `app/api/v1/admin/experiments.py` | A/B experiment admin endpoints |
| Admin metrics | `app/api/v1/admin/metrics_dashboard.py` | Metrics dashboard endpoints |
| App entry | `app/main.py` | FastAPI application entry point, router mounting, middleware, health endpoint |

## Commands

```bash
# Run API tests
uv run pytest tests/test_chat_api.py tests/test_auth_api.py tests/test_admin_api.py
uv run pytest tests/api/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. API-specific conventions:

- **Type hints**: All route handlers must have complete type annotations.
- **Async routes**: All FastAPI routes must be `async`.
- **Response models**: Use Pydantic response models for all endpoints.
- **Error handling**: Use FastAPI exception handlers; never return raw exceptions.

## Testing Patterns

- Test each endpoint with mocked services.
- Verify SSE streaming format in chat tests.
- Test auth middleware and permission checks.
- Mock WebSocket connections for websocket tests.

## Conventions

- **Versioning**: All routes under `/api/v1/` prefix.
- **SSE format**: Chat responses use SSE with `data:` prefix and JSON payload.
- **Auth**: Use OAuth2 bearer tokens; validate in dependency functions.
- **Admin routes**: All admin routes under `/api/v1/admin/` with admin auth requirements.

## Anti-Patterns

- **Business logic in routes**: Keep routes thin; delegate to services.
- **Missing response models**: Always define response models for type safety.
- **Synchronous blocking**: Never use sync I/O in async route handlers.

## Related Files

- `app/services/` — Business logic services consumed by API routes.
- `app/schemas/` — Pydantic schemas for request/response validation.
- `app/core/security.py` — JWT token creation and validation.
