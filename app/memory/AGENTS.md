# AGENTS.md - Memory System

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- `AGENTS.md` is a living document. Update this file when adding or modifying memory system guidance.
- Keep module-specific content here; do not duplicate root-level rules.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for memory-system-specific guidance.
3. For architecture details, read [`docs/explanation/architecture/`](../../docs/explanation/architecture/).

## Overview

The memory system provides persistent, multi-tier memory for the agent:

- **Structured memory** (PostgreSQL): User profiles, preferences, interaction summaries, and extracted facts with confidence scores.
- **Vector conversation memory** (Qdrant): Semantic retrieval of past conversation turns for context injection.
- **Fact extraction pipeline**: Async Celery tasks extract structured facts from conversation turns using LLMs, with PII filtering and confidence gating.
- **Session summarization**: Dual-write summaries to both PostgreSQL and Qdrant for long-term retention.

## Key Files

| Task | File | Description |
|------|------|-------------|
| Structured memory CRUD | `@app/memory/structured_manager.py` | `UserProfile`, `UserPreference`, `InteractionSummary`, `UserFact` |
| Vector conversation memory | `@app/memory/vector_manager.py` | Qdrant `conversation_memory` collection; semantic search of chat history |
| Fact extraction | `@app/memory/extractor.py` | `FactExtractor` using LLM + JSON parsing; confidence filtering at 0.7 |
| Session summarization | `@app/memory/summarizer.py` | `SessionSummarizer`; dual-writes summary to PostgreSQL and Qdrant |
| Memory compaction | `@app/memory/compactor.py` | Compacts oversized memory context before prompt injection |
| Data models | `@app/models/memory.py` | SQLModel definitions for all memory entities |
| Async tasks | `@app/tasks/memory_tasks.py` | Celery tasks for async fact extraction and memory sync |

## Commands

```bash
# Run memory system tests
uv run pytest tests/memory/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Memory-specific conventions:

- **Type hints**: All CRUD methods in `structured_manager.py` and vector operations in `vector_manager.py` must have complete type annotations.
- **Async-only I/O**: All database and Qdrant operations must be `async`. No synchronous calls in memory managers.
- **PII filtering**: Use compiled regex patterns in `extractor.py`; do not recompile patterns on every call.
- **User isolation**: Every public CRUD method must accept and enforce `user_id` filtering at the manager layer.

## Testing Patterns

- **Structured memory**: Mock `AsyncSession` to verify CRUD operations and `user_id` isolation.
- **Vector memory**: Mock Qdrant client to verify write, retrieval, and delete logic.
- **Fact extractor**: Use stubbed LLM responses; cover JSON prompt parsing and confidence threshold filtering.
- **PII filtering**: Test regex guards for credit card numbers (`\b\d{13,19}\b`) and passwords (`password[:\s]*\S+`); verify extraction is skipped when PII is detected.
- **Celery tasks**: Verify `extract_and_save_facts` executes asynchronously without blocking SSE responses.

## Conventions

- **Confidence filter**: Facts with `confidence < 0.7` are discarded immediately after extraction.
- **PII guards**: `extractor.py` regex-filters credit card numbers and password patterns before calling LLM; if PII is detected, extraction is skipped for that turn.
- **Async Celery trigger**: `decider_node` triggers `extract_and_save_facts` via Celery after the turn ends; LLM calls do not block the SSE response.
- **User ID isolation**: All structured memory queries must filter by `user_id`. Never return cross-user data.
- **Dual-write summaries**: `SessionSummarizer` writes summaries to both PostgreSQL (`InteractionSummary`) and Qdrant (vector form).

## Experiment Variant Configuration (`memory_context_config`)

The `memory_context_config` parameter in `AgentState` allows experiment variants to override memory token budgets and compaction thresholds at runtime. This enables A/B tests to evaluate different context window allocations without code changes.

### Parameter Structure

`memory_context_config` is an optional `dict[str, Any]` carried in `AgentState` (see `@app/models/state.py`). It accepts the following override keys:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `memory_token_budget` | `int` | `2048` (from `settings.MEMORY_CONTEXT_TOKEN_BUDGET`) | Maximum tokens allocated to memory context injection. When exceeded, lowest-priority memory fields are pruned first. |
| `compaction_threshold` | `float` | `0.75` (from `settings.COMPACTION_THRESHOLD`) | Token utilization ratio that triggers session summarization in the decider node. |

### How Experiment Variants Use This Parameter

When an `experiment_variant_id` is present in `AgentState`, the graph layer may load variant-specific configuration into `memory_context_config`. The override flows through three layers:

1. **Graph node allocation** (`@app/graph/nodes.py`): `memory_node` passes `memory_context_config` to `MemoryTokenBudget.allocate()`, which applies the `memory_token_budget` override when pruning memory fields.

2. **Agent prompt building** (`@app/agents/base.py`): `BaseAgent._build_user_prompt()` extracts `memory_token_budget` from `memory_context_config` and uses it to cap the injected memory text. This affects both `_build_contextual_message()` (used by most agents) and the legacy contextual path.

3. **Compaction trigger** (`@app/graph/nodes.py`): `decider_node` reads `compaction_threshold` from `memory_context_config` and passes it to `SessionSummarizer.should_summarize()`. When utilization exceeds this threshold, the compactor replaces message history with a condensed summary.

### Memory Injection Priority

When pruning is required (token budget exceeded), fields are dropped in this priority order (lowest priority first):

1. `relevant_past_messages` - Vector-retrieved conversation history
2. `interaction_summaries` - Condensed session summaries
3. `structured_facts` - Extracted user facts
4. `preferences` - User preference key/value pairs
5. `user_profile` - Core user identity (never pruned)

### Cross-References

- `@app/models/state.py` — `AgentState` definition; `memory_context_config` field (line 80).
- `@app/agents/base.py` — Budget override extraction in `_format_memory_prefix()` (lines 242-243) and `_build_contextual_message()` (lines 309-310); `memory_context_config` parameter defined in `_build_user_prompt()` (line 164).
- `@app/graph/nodes.py` — `memory_node` allocation (lines 234-235) and `decider_node` compaction threshold override (lines 553-558).
- `@app/context/token_budget.py` — `MemoryTokenBudget.allocate()` implements priority-based pruning.
- `@app/core/config.py` — Default values: `MEMORY_CONTEXT_TOKEN_BUDGET = 2048`, `COMPACTION_THRESHOLD = 0.75`.

## Anti-Patterns

- **Oversized `memory_context` in prompts**: Use `compactor.py` to trim context before injection. Never stuff unbounded history into prompts.
- **Synchronous LLM calls in extraction**: Always trigger fact extraction through Celery tasks. Synchronous LLM calls block the response stream.
- **Unfiltered bulk queries**: Never return unfiltered bulk query results from `structured_manager.py`; always enforce `user_id` filtering.

## Related Files

- `@app/graph/nodes.py`: `memory_node` injects and persists memory around graph execution.
- `@app/tasks/memory_tasks.py`: `extract_and_save_facts` is triggered asynchronously after `decider_node` completes.
