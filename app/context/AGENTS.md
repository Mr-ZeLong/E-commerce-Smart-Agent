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
| Observation masking | `app/context/masking.py` | Masks sensitive observations before LLM injection |
| Token budget | `app/context/token_budget.py` | `MemoryTokenBudget` for context allocation across memory tiers |

## Code Style

General Python rules are defined in the root `AGENTS.md`. Context-specific conventions:

- **Type hints**: All context manipulation functions must be fully typed.
- **Performance**: Context operations are on the hot path; optimize for minimal overhead.
- **Immutability**: Prefer creating new context objects over mutating existing ones.

## Testing Patterns

- Test masking logic with various input patterns (PII, secrets, etc.).
- Verify token budget allocation respects limits and priorities.
- Benchmark context operations for performance regression detection.

## Conventions

- **Masking priority**: Mask PII and secrets before any other transformations.
- **Token allocation**: Allocate memory context tokens in priority order: user profile > preferences > structured facts > interaction summaries > relevant past messages.
- **Truncation strategy**: When exceeding budget, truncate from lowest priority upward (oldest memory first).

## Anti-Patterns

- **Unbounded context**: Never pass unbounded context to LLM; always apply token budget.
- **Over-masking**: Be precise with masking to avoid removing useful context.
- **In-place mutation**: Avoid mutating context dictionaries in place; return new objects.

## Related Files

- `app/memory/compactor.py` — Unconditionally compacts conversation history to reduce context size.
- `app/agents/base.py` — Builds memory context using token budget allocation.
