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
| Checkpoint persistence | `@app/graph/checkpointer.py` | OptimizedRedisCheckpoint with diff-based storage, compression, and TTL management for LangGraph checkpoints |
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
- **File length**: Keep node files under 400 lines; split by responsibility (routing, memory, synthesis, etc.). Note: `nodes.py` is currently 627 lines and contains 6 node builder categories: router, memory, supervisor, synthesis, evaluator, and decider.

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

## State Isolation

Agent subgraphs receive only a filtered subset of `AgentState` keys to enforce state isolation and prevent context leakage between agents. This is controlled by two constants defined in `@app/graph/workflow.py` (lines 27-51).

| Constant | Purpose |
|----------|---------|
| `_COMMON_ALLOWED_KEYS` | Base keys shared by all agents (user context, memory, intent metadata, iteration counters, etc.) |
| `_AGENT_ALLOWED_KEYS` | Per-agent overrides that extend `_COMMON_ALLOWED_KEYS` with domain-specific keys |

### `_COMMON_ALLOWED_KEYS`

Keys present in every agent's filtered state:
- `question`, `user_id`, `thread_id`
- `history`, `memory_context`, `memory_context_config`
- `intent_result`, `slots`
- `iteration_count`, `experiment_variant_id`
- `context_tokens`, `context_utilization`

### `_AGENT_ALLOWED_KEYS` examples

| Agent | Additional keys beyond common |
|-------|------------------------------|
| `policy_agent` | `retrieval_result` |
| `order_agent` | `order_data`, `retrieval_result` |
| `logistics` | `order_data`, `retrieval_result` |
| `product` | `product_data`, `retrieval_result` |
| `cart` | `cart_data`, `retrieval_result` |
| `account`, `payment`, `complaint` | `retrieval_result` |

The subgraph wrapper (`@app/graph/subgraphs.py`) and direct agent nodes (`_build_agent_node` in `@app/graph/nodes.py`) use these lists to filter the full `AgentState` via `_filter_state()` before passing it to the agent's `process()` method. Any state updates returned by the agent are then merged back into the parent graph state via `Command(update=...)`.

## Anti-Patterns

- **Monolithic node files**: Avoid node files exceeding 400 lines; split by responsibility (routing, memory, synthesis, etc.).
- **Over-coupled nodes**: Do not let a single node handle multiple unrelated responsibilities.
- **Duplicate try/except blocks**: Consolidate repeated error handling into shared helpers or context managers.
- **State mutation in nodes**: Do not mutate `AgentState` in place inside node functions; always return changes via `Command(update=...)`.

## Related Files

- `@app/intent/multi_intent.py` — `are_independent()` controls LangGraph parallel dispatch decisions.
- `@app/safety/AGENTS.md` — `synthesis_node` uses `OutputModerator` for output content moderation.
