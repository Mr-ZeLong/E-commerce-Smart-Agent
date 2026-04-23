# AGENTS.md - Services

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for business services.
- Update this file in the same PR when adding new services or changing service conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for service-specific guidance.

## Overview

Business logic services that orchestrate domain operations. Services sit between API routes and tools/models, encapsulating business rules and workflows.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Auth service | `@app/services/auth_service.py` | Authentication and authorization logic |
| Order service | `@app/services/order_service.py` | Order management and query |
| Refund service | `@app/services/refund_service.py` | Refund processing workflows |
| Status service | `@app/services/status_service.py` | Thread status polling |
| Admin service | `@app/services/admin_service.py` | Admin operations and user management |
| Online evaluation | `@app/services/online_eval.py` | Real-time evaluation from user feedback |
| Continuous improvement | `@app/services/continuous_improvement.py` | CI pipeline for prompt and model optimization |
| Experiment management | `@app/services/experiment.py` | A/B experiment lifecycle management |
| Experiment assigner | `@app/services/experiment_assigner.py` | User variant assignment for experiments |

## Commands

```bash
# Run service tests
uv run pytest tests/test_order_service.py tests/test_refund_service.py tests/test_auth_service.py tests/test_status_service.py tests/test_admin_service.py
uv run pytest tests/services/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Service-specific conventions:

- **Type hints**: All service methods must have complete type annotations.
- **Async**: All service methods must be `async`.
- **Error handling**: Use custom exceptions for domain errors; catch and convert to HTTP errors at API layer.
- **User isolation**: All queries must filter by `user_id` where applicable.

## Testing Patterns

- Mock database sessions and external services in unit tests.
- Test business rules and edge cases (invalid state transitions, permission checks).
- Verify service orchestration (e.g., refund workflow steps).

## Conventions

- **Service layer**: Services encapsulate business logic; they do not handle HTTP concerns.
- **Transaction boundary**: Each service method should represent a single transaction boundary.
- **Idempotency**: Design service operations to be idempotent where possible.
- **DTOs**: Use Pydantic models for service inputs/outputs rather than raw dicts.

## Anti-Patterns

- **HTTP concerns in services**: Services should not handle status codes or headers.
- **Direct DB access from routes**: Routes must use services, not access DB directly.
- **Synchronous I/O**: All external calls must be async.

## Related Files

- `@app/api/v1/` — API routes that consume services.
- `@app/models/` — Data models used by services.
- `@app/tools/` — Tools that services may delegate to.
