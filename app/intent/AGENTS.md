# AGENTS.md - Intent Recognition

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules, commands, and conventions.

## Maintenance Contract

- Update this file when adding new intent components, changing pipeline order, or introducing new testing patterns.
- Keep this file focused on module-specific guidance. Do not duplicate root-level rules.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules.
2. Read this file for intent-recognition-specific guidance.

## Overview

Intent recognition pipeline that classifies user messages into intents, determines whether multiple intents can execute in parallel, validates slots, detects topic drift, and enforces safety checks before any LLM invocation.

## Key Files

| Task | File | Description |
|------|------|-------------|
| Main pipeline | `@app/intent/service.py` | `IntentRecognitionService` with Redis session cache |
| Intent classifier | `@app/intent/classifier.py` | LLM-based intent classifier |
| Multi-intent / independence | `@app/intent/multi_intent.py` | `are_independent()` drives LangGraph parallel dispatch |
| Clarification engine | `@app/intent/clarification.py` | Clarification prompts when slots are missing |
| Slot validator | `@app/intent/slot_validator.py` | Slot value validation |
| Topic switch detector | `@app/intent/topic_switch.py` | Topic drift detection |
| Safety filter | `@app/intent/safety.py` | Input safety review before LLM calls |
| State models | `@app/intent/models.py` | Intent/slot state models |
| Config | `@app/intent/config.py` | Intent module configuration |
| Few-shot loader | `@app/intent/few_shot_loader.py` | Few-shot example loading |

## Commands

```bash
# Run intent module tests
uv run pytest tests/intent/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Intent-specific conventions:

- **Type hints**: All pipeline methods and classifier outputs must be fully typed.
- **Immutability**: Never mutate global state in classifiers; write all outputs to the passed `state` object.
- **LLM guardrails**: All LLM-based intent classifiers must include structured output schemas and validation.
- **Performance**: Cache high-frequency safety rules; avoid runtime regex compilation inside hot loops.

## Testing Patterns

- **Classifier tests**: Mock LLM responses to cover single-intent, multi-intent, and unknown-intent scenarios.
- **Multi-intent tests**: `tests/intent/test_multi_intent.py` validates the independence judgment matrix via `are_independent()`.
- **Clarification tests**: Cover missing slots, clarification prompt generation, and termination conditions.
- **Safety tests**: Partition by concern (sensitive keywords, injection attacks, PII leakage) into separate test files or `describe` blocks.

## Conventions

- **Pipeline order (`recognize()`)**: `SafetyFilter` → `Redis cache` → `Classifier / MultiIntent` → `TopicSwitchDetector` → `SlotValidator`. `ClarificationEngine` is invoked separately via `clarify()` when slots are missing.
- **Parallel dispatch**: `are_independent()` returning `True` causes `@app/graph/parallel.py` to construct `Send` nodes for parallel execution.
- **State model writes**: Intent and slot results are explicitly written to `AgentState.intent_result` / `AgentState.slots`.
- **Safety first**: `safety.py` executes before any LLM call to intercept violations.

## Anti-Patterns

- **Rule bloat in safety**: Do not accumulate large rule sets in `safety.py` that degrade performance; hoist high-frequency rules or cache results.
- **Global state mutation in classifier**: Never mutate global or module-level state in `classifier.py`; all outputs must be written to the passed `state` object.

## Related Files

- `@app/graph/parallel.py` — consumes `are_independent()` to construct `Send` for multi-intent parallel execution.
