# AGENTS.md - Utils

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for utility functions.
- Update this file in the same PR when adding new utilities or changing utility conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for utility-specific guidance.

## Overview

Shared utility functions used across the application. Keep utilities stateless and free of business logic.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Order utilities | `@app/utils/order_utils.py` | Order-related helper functions |

## Commands

```bash
# Run utility tests
uv run pytest tests/utils/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Utility-specific conventions:

- **Pure functions**: Utilities should be pure functions where possible.
- **Type hints**: All utility functions must have complete type annotations.
- **No side effects**: Utilities should not have side effects (no DB writes, no I/O).
- **Reusability**: Design utilities for reuse across multiple modules.

## Testing Patterns

- Unit test utilities with various inputs including edge cases.
- Mock any external dependencies.

## Conventions

- **Naming**: Use descriptive function names that indicate the operation.
- **Input validation**: Validate inputs and raise `ValueError` for invalid arguments.
- **Documentation**: Document expected input formats and return types.

## Anti-Patterns

- **Business logic in utilities**: Utilities should be generic, not domain-specific.
- **Mutable default arguments**: Never use mutable default arguments in utility functions.
- **Hidden I/O**: Utilities should not perform I/O; pass data in and out.

## Related Files

- `@app/core/utils.py` — Core utilities (cross-cutting concerns like `utc_now`, `build_thread_id`).
