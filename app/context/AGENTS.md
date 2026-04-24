# AGENTS.md - Context

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for context engineering.
- Update this file in the same PR when adding new context management features.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for context-specific guidance.

## Overview

Context engineering utilities for managing LLM context windows, including observation masking and token budget allocation.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Observation masking | `@app/context/masking.py` | Masks sensitive observations before LLM injection |
| Token budget | `@app/context/token_budget.py` | `MemoryTokenBudget` for context allocation across memory tiers |
| Memory context truncation | `@app/agents/base.py` | `_truncate_parts_by_budget()` — drops parts from end until token count is within `MEMORY_CONTEXT_TOKEN_BUDGET`; preserves last part (user question) |
| PII filter | `@app/context/pii_filter.py` | PII detection and filtering with regex patterns for credit cards, Chinese mobile, ID numbers, passports, email, SSN, bank accounts; GDPR compliance utilities |

## Commands

```bash
# Run context module tests
uv run pytest tests/context/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Context-specific conventions:

- **Pure functions**: Context utilities should be pure functions without side effects.
- **Type hints**: All context functions must have complete type annotations.
- **Immutability**: Return new context objects rather than mutating inputs in place.

## Testing Patterns

- Test token budget allocation with various memory sizes.
- Verify masking correctly hides sensitive data while preserving structure.
- Test truncation behavior at boundary conditions (exact budget, over budget by 1 token).
- Mock LLM token counting for deterministic tests.

## Conventions

- **Masking priority**: Mask PII and secrets before any other transformations.
- **Token allocation**: Allocate memory context tokens in priority order: user profile > preferences > structured facts > interaction summaries > relevant past messages.
- **Truncation strategy**: When exceeding budget, truncate from lowest priority upward (oldest memory first).

## Anti-Patterns

- **Unbounded context**: Never pass unbounded context to LLM; always apply token budget.
- **Over-masking**: Be precise with masking to avoid removing useful context.
- **In-place mutation**: Avoid mutating context dictionaries in place; return new objects.

## Related Files

- `@app/memory/compactor.py` — Unconditionally compacts conversation history to reduce context size.
- `@app/agents/base.py` — Builds memory context using token budget allocation.
