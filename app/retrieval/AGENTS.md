# AGENTS.md - Retrieval

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the RAG retrieval system.
- Update this file in the same PR when adding new retrieval components or changing retrieval strategies.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for retrieval-specific guidance.

## Overview

Hybrid RAG retrieval system combining dense embeddings, sparse embeddings (BM25), reranking, and query rewriting for semantic search across product catalog and knowledge base.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Hybrid retriever | `@app/retrieval/retriever.py` | `HybridRetriever` combining dense + sparse + reranker |
| Embeddings | `@app/retrieval/embeddings.py` | Dense embedding model creation and caching |
| Sparse embedder | `@app/retrieval/sparse_embedder.py` | Sparse/BM25 embedding generation |
| Reranker | `@app/retrieval/reranker.py` | Cross-encoder reranking for result refinement |
| Query rewriter | `@app/retrieval/rewriter.py` | LLM-based query rewriting and expansion |
| Qdrant client | `@app/retrieval/client.py` | Qdrant vector store client wrapper |

## Commands

```bash
# Run retrieval module tests
uv run pytest tests/retrieval/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Retrieval-specific conventions:

- **Type hints**: All retrieval methods and embedding functions must have complete type annotations.
- **Async-only I/O**: All Qdrant and model operations must be `async`.
- **Caching**: Cache embedding models and tokenizers to avoid repeated initialization.

## Testing Patterns

- Mock Qdrant client for retrieval tests.
- Use stubbed embedding models to avoid loading real models in unit tests.
- Test query rewriting with mock LLM responses.
- Verify hybrid scoring (dense + sparse) logic.

## Conventions

- **Hybrid retrieval**: Combine dense embeddings (semantic similarity) with sparse embeddings (keyword matching) for optimal recall.
- **Reranking**: Apply cross-encoder reranking to top-k candidates from hybrid retrieval for precision.
- **Query rewriting**: Expand and disambiguate user queries before retrieval to improve match quality.
- **Collection naming**: Use consistent Qdrant collection names (`product_catalog`, `conversation_memory`, `knowledge_chunks`).

## Anti-Patterns

- **Synchronous embedding calls**: Always use async embedding generation to avoid blocking.
- **Unbounded retrieval**: Limit retrieval to top-k results (typically 5-10) to avoid context overflow.
- **Ignoring reranking**: Skipping reranking reduces precision; always apply to hybrid results.

## Related Files

- `@app/agents/policy.py` — Uses retrieval for policy Q&A.
- `@app/tools/product_tool.py` — Uses retrieval for product catalog search.
- `@app/memory/vector_manager.py` — Uses retrieval for conversation memory.
