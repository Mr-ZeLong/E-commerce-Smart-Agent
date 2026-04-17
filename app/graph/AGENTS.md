# AGENTS.md - LangGraph Workflow

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is module-specific guidance for LangGraph workflow and node orchestration.
- Keep it concise; push broad or conditional guidance to the root `AGENTS.md`.
- Update this file in the same PR when workflow architecture, node patterns, or dispatch conventions materially change.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for module-specific LangGraph guidance.
3. For architecture details, read [`docs/explanation/architecture/`](../../docs/explanation/architecture/).

## Overview

LangGraph workflow compiler and runtime node layer. Responsible for Agent Subgraph orchestration and multi-intent parallel dispatch.

## Key Files

| Task | File | Description |
|------|------|-------------|
| Graph compilation | `@app/graph/workflow.py` | Dual-path compilation: Supervisor mode and legacy compatibility mode |
| Node definitions | `@app/graph/nodes.py` | router / memory / supervisor / synthesis / evaluator / decider |
| Agent Subgraph standard | `@app/graph/subgraphs.py` | Wraps `BaseAgent` into an independent `StateGraph` |
| Parallel dispatch | `@app/graph/parallel.py` | Multi-intent independence judgment and `Send` batch distribution |

## Commands

```bash
# Graph unit tests and integration tests
uv run pytest tests/graph/ tests/integration/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Graph-specific conventions:

- **Type hints**: All node builder functions and graph compilation methods must have complete type annotations.
- **Node purity**: Node functions should be deterministic and free of side effects; all state changes are returned via `update`.
- **Command returns**: Always use `Command(goto=..., update=...)` instead of mutating input state in place.
- **File length**: Keep node files under 400 lines; split by responsibility (routing, memory, synthesis, etc.).

## Testing Patterns

- Node unit tests must mock `LLM` and assert return values conform to `Command(goto=..., update=...)` structure.
- Use `@tests/graph/test_workflow.py` to verify workflow compilation results and state transitions.
- Integration tests in `@tests/integration/test_workflow_invoke.py` cover end-to-end multi-intent scenarios.
- When testing parallel dispatch, construct `AgentState` containing multiple intents and assert the `Send` list length and target nodes.

## Conventions

- **Dual-mode compilation**: When `supervisor_agent=None`, falls back to the legacy path (`router_node` routes directly to specific agents).
- **Node return standard**: Always return `Command(goto=..., update=...)`.
- **Subgraph standard**: Each expert agent is wrapped as an independent `StateGraph`, consuming a subset of `AgentState` and producing `{"sub_answers": [...]}` merged via `operator.add`.
- **Parallel dispatch**: `@app/graph/parallel.py` calls `are_independent()` from `@app/intent/multi_intent.py` to decide parallel execution.
- **Node purity**: Node builders should avoid side effects; state modifications must be returned explicitly via the `update` dict.

## Anti-Patterns

- **Monolithic node files**: Avoid node files exceeding 400 lines; split by responsibility (routing, memory, synthesis, etc.).
- **Over-coupled nodes**: Do not let a single node handle multiple unrelated responsibilities.
- **Duplicate try/except blocks**: Consolidate repeated error handling into shared helpers or context managers.
- **State mutation in nodes**: Do not mutate `AgentState` in place inside node functions; always return changes via `Command(update=...)`.

## Related Files

- `@app/intent/multi_intent.py` — `are_independent()` controls LangGraph parallel dispatch decisions.
