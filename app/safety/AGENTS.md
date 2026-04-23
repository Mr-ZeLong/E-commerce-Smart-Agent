# AGENTS.md - Safety

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the safety moderation system.
- Update this file in the same PR when adding new moderation layers, changing detection rules, or modifying the output pipeline.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for safety-specific guidance.

## Overview

Multi-layer output content moderation system that filters agent responses before they reach users. The pipeline runs 4 layers sequentially for defense in depth:

1. **Rule-based layer** — PII detection and sensitive keyword filtering
2. **Regex pattern layer** — Injection, code, and adversarial pattern detection
3. **Embedding similarity layer** — Semantic similarity to known unsafe content
4. **LLM judge layer** — High-confidence arbiter for borderline cases

## Key Files

| Role | File | Notes |
|------|------|-------|
| Orchestrator | `@app/safety/output_moderator.py` | `OutputModerator` class; coordinates 4-layer pipeline |
| Base types | `@app/safety/types.py` | `LayerResult`, `ModerationResult`, `calculate_risk_level()` |
| Layer 1: Rules | `@app/safety/rules.py` | `RuleBasedLayer` — PII and keyword filtering (<10ms) |
| Layer 2: Patterns | `@app/safety/patterns.py` | `RegexPatternLayer` — Regex-based injection/code detection |
| Layer 3: Embeddings | `@app/safety/embeddings.py` | `EmbeddingSimilarityLayer` — Semantic similarity check |
| Layer 4: LLM Judge | `@app/safety/llm_judge.py` | `LLMJudgeLayer` — LLM-based content arbitration |

## Commands

```bash
# Run safety module tests
uv run pytest tests/safety/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Safety-specific conventions:

- **Type hints**: All moderation methods must return typed `LayerResult` or `ModerationResult`.
- **Latency targets**: Layer 1 (rules) must complete in <10ms; Layer 2 (patterns) in <5ms.
- **Layer isolation**: Each layer must be independently testable and replaceable.
- **Async compatibility**: Layer 4 (LLM judge) is async; layers 1-3 are sync for low latency.

## Testing Patterns

- Test each layer independently with known safe/unsafe content.
- Verify `ModerationResult` structure for all layer combinations.
- Test PII regex patterns with synthetic data (credit cards, phone numbers, SSNs).
- Mock LLM judge in unit tests to avoid non-determinism.
- Test risk score thresholds (0.3=medium, 0.7=high).

## Conventions

- **Pipeline order**: Rule → Pattern → Embedding → LLM Judge (sequential, early exit on block).
- **Risk levels**: `low` (<0.3), `medium` (0.3-0.7), `high` (>0.7).
- **Blocking**: Any layer can block; blocked responses return `replacement_text` with a system message.
- **Layer 4 invocation**: LLM judge is only invoked when layers 1-3 show elevated risk but do not definitively block.
- **PII patterns**: Precompiled regex for credit cards (`\b\d{16,19}\b`), SSN (`\b\d{3}-\d{2}-\d{4}\b`), phone (`\b1[3-9]\d{9}\b`).

## Anti-Patterns

- **Skipping layers**: Do not bypass lower layers to save time; defense in depth requires all layers.
- **Hardcoded block messages**: Use configurable `block_message` in `OutputModerator` constructor.
- **Synchronous LLM calls**: Layer 4 must be async to avoid blocking the event loop.
- **Overly broad regex**: Patterns that generate false positives degrade user experience.

## Related Files

- `@app/agents/base.py` — Uses `OutputModerator` in agent response pipeline.
- `@app/graph/nodes.py` — `synthesis_node` invokes `OutputModerator` before streaming responses.
- `@app/intent/safety.py` — Input safety filter (complements output moderation).
