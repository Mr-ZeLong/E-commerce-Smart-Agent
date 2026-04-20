# AGENTS.md - Schemas

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for Pydantic request/response schemas.
- Update this file in the same PR when adding new API schemas or modifying existing ones.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for schema-specific guidance.

## Overview

Pydantic v2 request and response schemas for API validation. Defines structured data models for authentication, chat, and admin endpoints.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Auth schemas | `app/schemas/auth.py` | `LoginRequest`, `RegisterRequest`, `TokenResponse`, `UserInfoResponse` |
| Admin schemas | `app/schemas/admin.py` | Admin-related request/response schemas |
| Agent config schemas | `app/schemas/agent_config.py` | Agent configuration schemas |
| Status schemas | `app/schemas/status.py` | Thread status response schema |

## Code Style

General Python rules are defined in the root `AGENTS.md`. Schema-specific conventions:

- **Type hints**: All fields must have explicit type annotations using Pydantic v2 types.
- **Validation**: Use Pydantic field validators for complex validation logic.
- **Documentation**: Add `Field(description=...)` to all fields for OpenAPI documentation.

## Testing Patterns

- Test schema validation with valid and invalid inputs.
- Verify JSON serialization/deserialization round-trips.
- Test field validators with edge cases.

## Conventions

- **Request schemas**: Use `*Request` suffix for request bodies.
- **Response schemas**: Use `*Response` suffix for response models.
- **Nested models**: Define nested models inline or in separate files for reuse.
- **Optional fields**: Use `Optional` or `| None` for nullable fields; provide sensible defaults.

## Anti-Patterns

- **Business logic in schemas**: Schemas should only validate and structure data; no business logic.
- **Using dicts instead of schemas**: Always use Pydantic models for API inputs/outputs.
- **Missing validation**: Always validate user input at the schema level.

## Related Files

- `app/api/v1/schemas.py` — API-specific request/response schemas (legacy location).
- `app/api/v1/auth.py` — Uses auth schemas for login/register endpoints.
- `app/models/` — SQLModel database models (distinct from API schemas).
