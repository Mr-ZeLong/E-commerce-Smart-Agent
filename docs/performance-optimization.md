# Performance Optimization Guide

## Overview

This document describes the performance optimization strategy for the E-commerce Smart Agent. The target SLOs are:

- **P95 latency < 500ms** for chat endpoint
- **P99 latency < 1000ms** for chat endpoint
- **Cost reduction 20%** via caching and batching

## Current Architecture Bottlenecks

### 1. Sequential Embedding Generation

The hybrid retriever (`app/retrieval/retriever.py`) previously generated dense and sparse embeddings sequentially. Each embedding call can take 20-50ms, so sequential execution doubled retrieval latency.

**Optimization**: Parallelize dense and sparse embedding creation using `asyncio.gather`.

**Impact**: ~30-50ms reduction per retrieval call.

### 2. Post-Streaming Observability Blocking

The chat endpoint (`app/api/v1/chat.py`) performed multiple sequential database writes after SSE streaming completed:
- Graph execution logging
- Per-node latency logging
- Experiment metrics
- Review ticket creation
- Token usage logging

These blocked the HTTP connection from closing.

**Optimization**: Move all post-streaming DB writes to a Celery task (`app/tasks/observability_tasks.py`).

**Impact**: ~50-150ms reduction in perceived latency (connection closes immediately after `[DONE]`).

### 3. Intent Recognition Without Caching

Every chat request called the intent recognition service, even for identical queries. This involved an LLM or classifier call.

**Optimization**: Cache intent results in Redis with a 1-hour TTL. Check cache before calling intent service.

**Impact**: Eliminates intent service latency for repeated queries (~20-80ms).

### 4. Synchronous Supervisor Logging

The supervisor node (`app/graph/nodes.py`) awaited a database write for every routing decision.

**Optimization**: Fire-and-forget supervisor decision logging using `asyncio.create_task`.

**Impact**: ~5-15ms reduction per multi-turn conversation.

## Caching Strategy

### Redis Cache Layers

| Cache Name | TTL | Use Case |
|------------|-----|----------|
| Intent | 1 hour | Repeated query intent recognition |
| Profile | 5 minutes | User profile lookups |
| Facts | 5 minutes | User fact retrieval |
| Preferences | 5 minutes | User preference retrieval |
| Summaries | 5 minutes | Interaction summary retrieval |
| Retrieval | 10 minutes | RAG retrieval results (when not multi-query) |
| Vector Search | 5 minutes | Qdrant vector search results |

### Cache Invalidation

- **Write-through**: Cache is updated when data is written (e.g., `save_user_fact` invalidates facts cache).
- **TTL-based**: All caches have automatic expiration.
- **Manual invalidation**: Admin operations can trigger cache flushes.

## Database Query Optimization

### N+1 Prevention

The memory node (`build_memory_node`) fetches four structured memory types in parallel:
1. User profile
2. User preferences
3. User facts
4. Recent summaries

Vector memory searches (summary + message) are also parallelized.

No N+1 queries were found in the critical path. All agent nodes use batched queries or single lookups.

## Async Processing

### Celery Tasks (Non-Critical Path)

| Task | Trigger | Description |
|------|---------|-------------|
| `observability.log_chat_observability` | After chat SSE | Execution logs, metrics, review tickets |
| `memory.extract_and_save_facts` | After decider node | Fact extraction from conversation |
| `evaluation.shadow_test` | After chat SSE | Shadow graph comparison (if enabled) |
| `memory.prune_vector_memory` | Daily (beat) | Old vector cleanup |

### Fire-and-Forget Patterns

- Vector upserts (user + assistant messages)
- Supervisor decision logging
- Shadow testing

## Performance Testing

### Running Tests

```bash
# Run all performance tests
uv run pytest tests/performance/ -v

# Run with detailed timing
uv run pytest tests/performance/ -v --durations=0
```

### Test Coverage

- `test_retrieval_p95_under_100ms`: Hybrid retrieval latency
- `test_memory_node_p95_under_50ms`: Memory node parallel query latency
- `test_cache_reduces_latency`: Cache hit vs miss comparison
- `test_chat_endpoint_p95_under_500ms`: End-to-end API latency (mocked graph)

### CI Integration

Performance tests run on every PR and daily at 02:00 UTC via `.github/workflows/performance.yml`.

## Monitoring

### Key Metrics

- `chat_latency_seconds` (P95/P99) — overall endpoint latency
- `node_latency_seconds` — per-node latency breakdown
- `cache_hit_ratio` — per-cache hit rate
- `redis_operation_latency` — Redis operation latency

### Alerting Thresholds

- P95 chat latency > 500ms for 5 minutes → page on-call
- Cache hit ratio < 50% for 10 minutes → investigate
- Redis connection errors > 10/minute → investigate

## Future Optimizations

1. **LLM Call Batching**: Evaluate batching multiple small LLM calls (e.g., confidence evaluation + synthesis) when they share the same context.
2. **Embedding Model Caching**: Cache embeddings for frequent queries at the embedding service level.
3. **Connection Pool Tuning**: Monitor and tune PostgreSQL and Qdrant connection pools based on load.
4. **Query Plan Analysis**: Add EXPLAIN ANALYZE monitoring for slow queries in structured memory.
5. **Model Quantization**: Evaluate smaller/faster embedding models for latency-critical paths.
