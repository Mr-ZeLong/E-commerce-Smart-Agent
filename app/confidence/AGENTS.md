# AGENTS.md - Confidence

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for confidence signal calculation.
- Update this file in the same PR when adding new confidence signals or modifying calculation logic.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for confidence-specific guidance.

## Overview

Confidence signal calculation for agent response quality assessment. Combines RAG retrieval confidence, LLM generation confidence, and emotional signals into a composite score.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Confidence signals | `@app/confidence/signals.py` | `calculate_rag_signal`, `calculate_llm_signal`, `calculate_emotion_signal`, `calculate_confidence_signals` |

## Commands

```bash
# Run confidence module tests
uv run pytest tests/test_confidence_signals.py
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Confidence-specific conventions:

- **Type hints**: All signal calculation functions must return `float` in range [0, 1].
- **Idempotency**: Confidence calculations should be deterministic for the same inputs.
- **Performance**: Keep calculations lightweight; they run on every agent response.

## Testing Patterns

- Test each signal independently with known inputs.
- Verify composite score is weighted average of individual signals.
- Test edge cases (empty retrieval, error responses, etc.).
- Mock external dependencies (retriever, LLM) in unit tests.

## Conventions

- **Signal range**: All individual signals and composite score must be in [0, 1].
- **Weighting**: Composite score = weighted average of RAG, LLM, and emotion signals.
- **Thresholds**: Low confidence (< 0.5) triggers human review or clarification.
- **Metadata**: Include individual signal breakdown in response metadata for debugging.

## Anti-Patterns

- **Over-complicated signals**: Keep signal calculation simple and interpretable.
- **Ignoring edge cases**: Handle empty retrievals and errors gracefully.
- **Blocking I/O**: Confidence calculation must not perform blocking I/O.

## Related Files

- `@app/agents/evaluator.py` — Uses `calculate_confidence_signals` for agent response evaluation.
- `@app/api/v1/chat_utils.py` — Embeds confidence metadata in SSE responses.
- `@app/models/state.py` — `AgentProcessResult` includes confidence scores.
