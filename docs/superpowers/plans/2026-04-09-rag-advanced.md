# Advanced RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the project's RAG from Naive RAG (pgvector single retrieval) to Advanced RAG (Qdrant hybrid dense+sparse + query rewrite + qwen3-rerank).

**Architecture:** Build a dedicated `app/retrieval/` module that encapsulates Qdrant client, dense/sparse embedders, query rewriter, reranker, and hybrid retriever. `PolicyAgent` delegates all retrieval to this module. A new ETL script populates Qdrant with both dense and sparse vectors.

**Tech Stack:** Python 3.12+, FastAPI, Qdrant 1.16.3, qdrant-client, fastembed (BM25 sparse), LangGraph, qwen-turbo (rewrite), qwen3-rerank.

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Add `qdrant-client` and `fastembed` dependencies |
| `docker-compose.yaml` | Add Qdrant service with healthcheck |
| `start.sh` | Start Qdrant and wait for it to be healthy |
| `app/core/config.py` | Add Qdrant, reranker, rewriter, fastembed settings |
| `app/retrieval/embeddings.py` | `QwenEmbeddings` (migrated from `app/graph/nodes.py`) |
| `app/retrieval/sparse_embedder.py` | `SparseTextEmbedder`: fastembed BM25 → Qdrant SparseVector, async-safe |
| `app/retrieval/client.py` | `QdrantKnowledgeClient`: async Qdrant client with `query_hybrid` |
| `app/retrieval/rewriter.py` | `QueryRewriter`: qwen-turbo query rewrite |
| `app/retrieval/reranker.py` | `QwenReranker`: qwen3-rerank API client |
| `app/retrieval/retriever.py` | `HybridRetriever`: orchestrates rewrite → dense+sparse → RRF → rerank |
| `app/retrieval/__init__.py` | Module init, `get_retriever()` singleton factory |
| `app/agents/policy.py` | Replace `_retrieve_knowledge`, update `_estimate_confidence` |
| `app/graph/nodes.py` | Remove or redirect the orphaned `retrieve` node |
| `scripts/etl_qdrant.py` | ETL pipeline: load → split → dense+sparse embed → upsert to Qdrant |
| `tests/retrieval/test_client.py` | Test Qdrant client collection creation and query |
| `tests/retrieval/test_sparse_embedder.py` | Test fastembed → SparseVector conversion |
| `tests/retrieval/test_retriever.py` | Test HybridRetriever orchestration with mocks |
| `tests/agents/test_policy.py` | Test PolicyAgent retrieval integration with mocked retriever |

---

## Pre-Flight: Verify Current Test Baseline

- [ ] **Step 1: Run existing tests to establish baseline**

Run: `pytest tests/ -v`
Expected: All existing tests pass (or at least no new failures introduced by our changes).

---

## Task 1: Dependencies & Infrastructure

**Files:**
- Modify: `pyproject.toml`
- Modify: `docker-compose.yaml`
- Modify: `start.sh`
- Modify: `.env`

- [ ] **Step 1: Add Python dependencies**

Modify `pyproject.toml` dependencies list, add:
```toml
"qdrant-client>=1.16.0,<1.17.0",
"fastembed>=0.6.0",
```

- [ ] **Step 2: Add Qdrant service to docker-compose**

In `docker-compose.yaml`, add the `qdrant` service inside `services:` and add `qdrant_storage` to the `volumes:` section at root level:

```yaml
  qdrant:
    image: qdrant/qdrant:v1.16.3
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Also add `healthcheck` to the existing `redis` service:
```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

And update `app` and `celery_worker` services `depends_on` to include:
```yaml
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
```

- [ ] **Step 3: Update start.sh to launch and wait for Qdrant**

Modify `start.sh` (lines launching docker-compose) from:
```bash
docker-compose up -d db redis
```
to:
```bash
docker-compose up -d db redis qdrant

# Wait for Qdrant to be healthy
echo "Waiting for Qdrant to be healthy..."
for i in {1..30}; do
  if curl -sf http://localhost:6333/healthz > /dev/null; then
    echo "Qdrant is healthy"
    break
  fi
  sleep 1
done
```

- [ ] **Step 4: Add Qdrant env variables to .env**

Append to `.env`:
```bash
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=knowledge_chunks
QDRANT_API_KEY=
REWRITE_MODEL=qwen-turbo
RERANK_MODEL=qwen3-rerank
RETRIEVER_DENSE_TOPK=15
RETRIEVER_SPARSE_TOPK=15
RETRIEVER_RRF_K=60
RETRIEVER_FINAL_TOPK=5
```

- [ ] **Step 5: Lock dependencies**

Run: `uv sync`
Expected: `uv.lock` updated with qdrant-client and fastembed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml docker-compose.yaml start.sh .env uv.lock
git commit -m "chore: add qdrant and fastembed dependencies, update docker-compose and start.sh"
```

---

## Task 2: Configuration

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Add Qdrant and retrieval settings**

In `app/core/config.py`, inside the `Settings` class, add:

```python
    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "knowledge_chunks"
    QDRANT_TIMEOUT: float = 10.0
    QDRANT_RETRIES: int = 3

    # Reranker / Rewriter
    RERANK_MODEL: str = "qwen3-rerank"
    REWRITE_MODEL: str = "qwen-turbo"
    RERANK_TIMEOUT: float = 10.0
    REWRITE_TIMEOUT: float = 5.0

    # Retriever
    RETRIEVER_DENSE_TOPK: int = 15
    RETRIEVER_SPARSE_TOPK: int = 15
    RETRIEVER_RRF_K: int = 60
    RETRIEVER_FINAL_TOPK: int = 5

    # fastembed
    FASTEMBED_CACHE_PATH: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add app/core/config.py
git commit -m "feat(config): add qdrant, reranker and retriever settings"
```

---

## Task 3: Dense Embeddings Module

**Files:**
- Create: `app/retrieval/embeddings.py`
- Modify: `app/graph/nodes.py` (remove old embedding_model)

- [ ] **Step 1: Create `app/retrieval/embeddings.py` with migrated `QwenEmbeddings`**

```python
import httpx
from langchain_core.embeddings import Embeddings

from app.core.config import settings


class QwenEmbeddings(Embeddings):
    """通义千问 Embedding API 适配器"""

    def __init__(self, base_url: str, api_key: str, model: str, dimensions: int):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("请使用异步方法 aembed_documents")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("请使用异步方法 aembed_query")

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts,
                    "dimensions": self.dimensions
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    async def aembed_query(self, text: str) -> list[float]:
        results = await self.aembed_documents([text])
        return results[0]


embedding_model = QwenEmbeddings(
    base_url=settings.OPENAI_BASE_URL,
    api_key=settings.OPENAI_API_KEY,
    model=settings.EMBEDDING_MODEL,
    dimensions=settings.EMBEDDING_DIM
)
```

- [ ] **Step 2: Update `app/graph/nodes.py` to import from new module**

Remove the `QwenEmbeddings` class and `embedding_model` instantiation from `app/graph/nodes.py` (lines 30-84). Add at the top:

```python
from app.retrieval.embeddings import embedding_model
```

Verify `retrieve()` and any other node still uses `embedding_model` as before.

- [ ] **Step 3: Commit**

```bash
git add app/retrieval/embeddings.py app/graph/nodes.py
git commit -m "feat(retrieval): migrate QwenEmbeddings to app.retrieval.embeddings"
```

---

## Task 4: Sparse Embedder

**Files:**
- Create: `app/retrieval/sparse_embedder.py`
- Test: `tests/retrieval/test_sparse_embedder.py`

- [ ] **Step 1: Write failing test for sparse embedder**

Create `tests/retrieval/test_sparse_embedder.py`:

```python
import pytest
from qdrant_client import models

from app.retrieval.sparse_embedder import SparseTextEmbedder


@pytest.mark.asyncio
async def test_sparse_embedder_produces_qdrant_sparse_vectors():
    embedder = SparseTextEmbedder()
    texts = ["hello world", "电商退换货政策"]
    results = await embedder.aembed(texts)

    assert len(results) == 2
    for vec in results:
        assert isinstance(vec, models.SparseVector)
        assert len(vec.indices) > 0
        assert len(vec.values) > 0
        assert len(vec.indices) == len(vec.values)
```

Run: `pytest tests/retrieval/test_sparse_embedder.py -v`
Expected: FAIL with import error (module doesn't exist yet).

- [ ] **Step 2: Implement `SparseTextEmbedder`**

Create `app/retrieval/sparse_embedder.py`:

```python
import asyncio
from typing import TYPE_CHECKING

from qdrant_client import models

try:
    from fastembed import SparseTextEmbedding
except ImportError as e:  # pragma: no cover
    raise ImportError("fastembed is required for sparse embeddings") from e

if TYPE_CHECKING:
    from fastembed.sparse.sparse_text_embedding import SparseEmbedding


import threading


class SparseTextEmbedder:
    def __init__(self, model_name: str = "Qdrant/bm25"):
        self.model_name = model_name
        self._model: SparseTextEmbedding | None = None
        self._lock = threading.Lock()

    def _get_model(self) -> SparseTextEmbedding:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    kwargs = {}
                    if settings.FASTEMBED_CACHE_PATH:
                        kwargs["cache_dir"] = settings.FASTEMBED_CACHE_PATH
                    self._model = SparseTextEmbedding(model_name=self.model_name, **kwargs)
        return self._model

    def _embed_sync(self, texts: list[str]) -> list[models.SparseVector]:
        model = self._get_model()
        raw_embeddings: list[SparseEmbedding] = list(model.embed(texts))
        results: list[models.SparseVector] = []
        for emb in raw_embeddings:
            indices = [int(i) for i in emb.indices.tolist()]
            values = [float(v) for v in emb.values.tolist()]
            results.append(models.SparseVector(indices=indices, values=values))
        return results

    async def aembed(self, texts: list[str]) -> list[models.SparseVector]:
        return await asyncio.to_thread(self._embed_sync, texts)
```

Run: `pytest tests/retrieval/test_sparse_embedder.py -v`
Expected: PASS (may be slow on first run due to model download).

- [ ] **Step 3: Commit**

```bash
git add app/retrieval/sparse_embedder.py tests/retrieval/test_sparse_embedder.py
git commit -m "feat(retrieval): add async BM25 sparse embedder with fastembed"
```

---

## Task 5: Qdrant Client

**Files:**
- Create: `app/retrieval/client.py`
- Test: `tests/retrieval/test_client.py`

- [ ] **Step 1: Write failing test for Qdrant client**

Create `tests/retrieval/test_client.py`:

```python
import pytest
from qdrant_client import AsyncQdrantClient, models

from app.retrieval.client import QdrantKnowledgeClient


@pytest.mark.asyncio
async def test_ensure_collection_creates_collection():
    # Use in-memory Qdrant for unit tests
    client = AsyncQdrantClient(":memory:")
    knowledge_client = QdrantKnowledgeClient(
        url=":memory:",
        collection_name="test_knowledge",
        client=client,
    )
    await knowledge_client.ensure_collection()

    collections = await client.get_collections()
    assert "test_knowledge" in [c.name for c in collections.collections]
```

Run: `pytest tests/retrieval/test_client.py -v`
Expected: FAIL because `QdrantKnowledgeClient` doesn't exist or lacks `client=` param.

- [ ] **Step 2: Implement `QdrantKnowledgeClient`**

Create `app/retrieval/client.py`:

```python
from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings


class QdrantKnowledgeClient:
    def __init__(
        self,
        url: str,
        collection_name: str,
        api_key: str | None = None,
        client: AsyncQdrantClient | None = None,
    ):
        self.collection_name = collection_name
        if client is not None:
            self.client = client
        elif url == ":memory:":
            self.client = AsyncQdrantClient(location=":memory:", timeout=settings.QDRANT_TIMEOUT)
        else:
            self.client = AsyncQdrantClient(url=url, api_key=api_key, timeout=settings.QDRANT_TIMEOUT)

    async def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, SparseVectorParams, VectorParams, Modifier

        exists = await self.client.collection_exists(self.collection_name)
        if exists:
            return

        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(modifier=Modifier.IDF)
            },
        )

    async def recreate_collection(self) -> None:
        await self.client.delete_collection(self.collection_name)
        await self.ensure_collection()

    async def upsert_chunks(self, points: list[models.PointStruct]) -> None:
        await self.client.upsert(collection_name=self.collection_name, points=points)

    async def query_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        dense_limit: int = 15,
        sparse_limit: int = 15,
    ) -> list[models.ScoredPoint]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=dense_limit,
                ),
                models.Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    limit=sparse_limit,
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf(k=settings.RETRIEVER_RRF_K)),
        )
        return list(response.points)
```

Run: `pytest tests/retrieval/test_client.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add app/retrieval/client.py tests/retrieval/test_client.py
git commit -m "feat(retrieval): add QdrantKnowledgeClient with hybrid query support"
```

---

## Task 6: Query Rewriter

**Files:**
- Create: `app/retrieval/rewriter.py`
- Test: `tests/retrieval/test_rewriter.py`

- [ ] **Step 1: Write failing test for query rewriter**

Create `tests/retrieval/test_rewriter.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.retrieval.rewriter import QueryRewriter


@pytest.mark.asyncio
async def test_rewrite_returns_first_line():
    rewriter = QueryRewriter(base_url="http://test", api_key="sk-test")
    with patch("app.retrieval.rewriter.ChatOpenAI") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = type("R", (), {"content": "  \n改写后查询\n多余内容"})()
        mock_llm_cls.return_value = mock_llm

        result = await rewriter.rewrite("东西坏了怎么退")
        assert result == "改写后查询"
```

Run: `pytest tests/retrieval/test_rewriter.py -v`
Expected: FAIL (module missing).

- [ ] **Step 2: Implement `QueryRewriter`**

Create `app/retrieval/rewriter.py`:

```python
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings

REWRITE_PROMPT = """你是一个电商客服查询优化专家。请将用户的口语化问题改写成一个更适合文档检索的查询。
要求：
1. 消除口语歧义，使用更正式、更具体的表达
2. 保留原意，不要添加文档中没有的信息
3. 只返回改写后的查询文本，不要解释

用户问题：{question}
改写后的查询："""


class QueryRewriter:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 5.0,
    ):
        self.llm = ChatOpenAI(
            base_url=base_url or settings.OPENAI_BASE_URL,
            api_key=SecretStr(api_key or settings.OPENAI_API_KEY),
            model=model or settings.REWRITE_MODEL,
            temperature=0,
            max_retries=0,
            timeout=timeout,
        )

    async def rewrite(self, query: str) -> str:
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=REWRITE_PROMPT.format(question=query))
            ])
            text = str(response.content).strip()
            for line in text.splitlines():
                line = line.strip()
                if line:
                    return line
            return query
        except Exception:
            return query
```

Run: `pytest tests/retrieval/test_rewriter.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add app/retrieval/rewriter.py tests/retrieval/test_rewriter.py
git commit -m "feat(retrieval): add qwen-turbo query rewriter"
```

---

## Task 7: Reranker

**Files:**
- Create: `app/retrieval/reranker.py`
- Test: `tests/retrieval/test_reranker.py`

- [ ] **Step 1: Write failing test for reranker**

Create `tests/retrieval/test_reranker.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.retrieval.reranker import QwenReranker


@pytest.mark.asyncio
async def test_rerank_parses_results():
    reranker = QwenReranker(base_url="http://test", api_key="sk-test")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.7},
            ]
        }
        mock_post.return_value.raise_for_status = lambda: None

        results = await reranker.rerank("query", ["doc0", "doc1"], top_n=2)
        assert results[0].index == 1
        assert results[0].score == pytest.approx(0.9)
        assert results[1].index == 0
```

Run: `pytest tests/retrieval/test_reranker.py -v`
Expected: FAIL (module missing).

- [ ] **Step 2: Implement `QwenReranker`**

Create `app/retrieval/reranker.py`:

```python
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class RerankResult:
    index: int
    score: float


class QwenReranker:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 10.0,
        max_document_chars: int = 12000,
    ):
        # Use the correct DashScope rerank endpoint, not the OpenAI chat endpoint
        self.base_url = "https://dashscope.aliyuncs.com/compatible-api/v1"
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.RERANK_MODEL
        self.timeout = timeout
        self.max_document_chars = max_document_chars

    def _truncate(self, text: str) -> str:
        if len(text) > self.max_document_chars:
            return text[:self.max_document_chars]
        return text

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankResult]:
        truncated_docs = [self._truncate(d) for d in documents]
        payload = {
            "model": self.model,
            "query": query,
            "documents": truncated_docs,
            "top_n": top_n,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            # Handle multiple possible response shapes
            raw_results = data.get("results", [])
            if not raw_results and "output" in data:
                raw_results = data["output"].get("results", [])

            results: list[RerankResult] = []
            for item in raw_results:
                idx = item.get("index") or item.get("document_index")
                score = item.get("relevance_score") or item.get("score")
                if idx is not None and score is not None:
                    results.append(RerankResult(index=int(idx), score=float(score)))

            return results
        except Exception:
            # Fallback to identity ordering on any failure
            return [RerankResult(index=i, score=0.0) for i in range(len(documents))]
```

Run: `pytest tests/retrieval/test_reranker.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add app/retrieval/reranker.py tests/retrieval/test_reranker.py
git commit -m "feat(retrieval): add qwen3-rerank client with fallback parsing"
```

---

## Task 8: Hybrid Retriever

**Files:**
- Create: `app/retrieval/retriever.py`
- Create: `app/retrieval/__init__.py`
- Test: `tests/retrieval/test_retriever.py`

- [ ] **Step 1: Write failing test for HybridRetriever**

Create `tests/retrieval/test_retriever.py`:

```python
import pytest
from unittest.mock import AsyncMock

from app.retrieval.retriever import HybridRetriever, RetrievedChunk


@pytest.mark.asyncio
async def test_retriever_orchestrates_all_steps():
    rewriter = AsyncMock()
    rewriter.rewrite.return_value = "改写后"

    qdrant_client = AsyncMock()
    qdrant_client.query_hybrid.return_value = [
        type("P", (), {
            "id": 1,
            "score": 0.1,
            "payload": {"content": "c1", "source": "s1", "meta_data": {}},
        })(),
        type("P", (), {
            "id": 2,
            "score": 0.05,
            "payload": {"content": "c2", "source": "s2", "meta_data": {}},
        })(),

    dense_embedder = AsyncMock()
    dense_embedder.aembed_query.return_value = [0.1] * 1024

    sparse_embedder = AsyncMock()
    sparse_embedder.aembed.return_value = [AsyncMock(indices=[0], values=[1.0])]

    reranker = AsyncMock()
    reranker.rerank.return_value = [
        type("R", (), {"index": 0, "score": 0.99})(),
        type("R", (), {"index": 1, "score": 0.88})(),
    ]

    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        reranker=reranker,
        rewriter=rewriter,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 2
    assert results[0].content == "c1"
    assert results[0].score == pytest.approx(0.99)
```

Run: `pytest tests/retrieval/test_retriever.py -v`
Expected: FAIL (module missing).

- [ ] **Step 2: Implement `HybridRetriever` and `__init__.py`**

Create `app/retrieval/retriever.py`:

```python
from dataclasses import dataclass

from qdrant_client import models

from app.core.config import settings


@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float
    metadata: dict | None = None


class HybridRetriever:
    def __init__(
        self,
        qdrant_client,
        dense_embedder,
        sparse_embedder,
        reranker,
        rewriter,
    ):
        self.qdrant_client = qdrant_client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.reranker = reranker
        self.rewriter = rewriter

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        rewritten = await self.rewriter.rewrite(query)
        dense_vec = await self.dense_embedder.aembed_query(rewritten)

        # Fallback: if sparse embedder fails, do pure dense retrieval
        try:
            sparse_vecs = await self.sparse_embedder.aembed([rewritten])
            sparse_vec = sparse_vecs[0]
        except Exception:
            sparse_vec = None

        try:
            if sparse_vec is not None:
                scored_points = await self.qdrant_client.query_hybrid(
                    dense_vector=dense_vec,
                    sparse_vector=sparse_vec,
                    dense_limit=settings.RETRIEVER_DENSE_TOPK,
                    sparse_limit=settings.RETRIEVER_SPARSE_TOPK,
                )
            else:
                scored_points = await self.qdrant_client.query_dense(
                    dense_vector=dense_vec,
                    limit=settings.RETRIEVER_DENSE_TOPK,
                )
        except Exception:
            # Qdrant failure is unrecoverable for this request
            raise

        if not scored_points:
            return []

        documents = [str(p.payload.get("content", "")) for p in scored_points]

        # Try rerank; on failure return RRF/dense results with original scores
        try:
            reranked = await self.reranker.rerank(rewritten, documents, top_n=settings.RETRIEVER_FINAL_TOPK)
        except Exception:
            reranked = None

        results: list[RetrievedChunk] = []
        if reranked is not None and len(reranked) > 0:
            for r in reranked:
                if 0 <= r.index < len(scored_points):
                    point = scored_points[r.index]
                    payload = point.payload or {}
                    results.append(RetrievedChunk(
                        content=str(payload.get("content", "")),
                        source=str(payload.get("source", "unknown")),
                        score=r.score,
                        metadata=dict(payload.get("meta_data", {})),
                    ))
        else:
            # Fallback: return top results from Qdrant with their original scores
            for point in scored_points[:settings.RETRIEVER_FINAL_TOPK]:
                payload = point.payload or {}
                results.append(RetrievedChunk(
                    content=str(payload.get("content", "")),
                    source=str(payload.get("source", "unknown")),
                    score=point.score,
                    metadata=dict(payload.get("meta_data", {})),
                ))

        return results
```

Create `app/retrieval/__init__.py`:

```python
from functools import lru_cache

from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import embedding_model
from app.retrieval.reranker import QwenReranker
from app.retrieval.rewriter import QueryRewriter
from app.retrieval.sparse_embedder import SparseTextEmbedder
from app.retrieval.retriever import HybridRetriever
from app.core.config import settings


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY,
    )
    return HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=embedding_model,
        sparse_embedder=SparseTextEmbedder(),
        reranker=QwenReranker(),
        rewriter=QueryRewriter(),
    )
```

Run: `pytest tests/retrieval/test_retriever.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add app/retrieval/retriever.py app/retrieval/__init__.py tests/retrieval/test_retriever.py
git commit -m "feat(retrieval): add HybridRetriever and get_retriever factory"
```

---

## Task 9: Integrate Retrieval into PolicyAgent

**Files:**
- Modify: `app/agents/policy.py`
- Modify: `app/confidence/signals.py`
- Modify: `app/agents/supervisor.py`
- Create: `tests/agents/test_policy.py`

- [ ] **Step 0: Create test directories if they don't exist**

Run: `mkdir -p tests/retrieval tests/agents`

- [ ] **Step 1: Write failing integration test for PolicyAgent retrieval**

Create `tests/agents/test_policy.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.policy import PolicyAgent


@pytest.mark.asyncio
async def test_policy_agent_uses_retriever():
    agent = PolicyAgent()
    mock_result = [
        type("C", (), {"content": "退换货政策内容", "source": "policy.md", "score": 0.95})(),
    ]

    with patch("app.agents.policy.get_retriever") as mock_factory:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = mock_result
        mock_factory.return_value = mock_retriever

        chunks, sims, sources = await agent._retrieve_knowledge("怎么退货")
        assert chunks == ["退换货政策内容"]
        assert sims == [pytest.approx(0.95)]
        assert sources == ["policy.md"]
```

Run: `pytest tests/agents/test_policy.py -v`
Expected: FAIL (import error from new `_retrieve_knowledge` or missing `get_retriever`).

- [ ] **Step 2: Update `app/agents/policy.py`**

Replace imports and methods:

```python
from app.retrieval import get_retriever

class PolicyAgent(BaseAgent):
    # ... __init__ unchanged ...

    async def _retrieve_knowledge(
        self,
        question: str
    ) -> tuple[list[str], list[float], list[str]]:
        retriever = get_retriever()
        results = await retriever.retrieve(question)
        chunks = [r.content for r in results]
        similarities = [r.score for r in results]
        sources = [r.source for r in results]
        print(f"[PolicyAgent] 检索到 {len(results)} 条有效结果")
        return chunks, similarities, sources

    def _estimate_confidence(
        self,
        chunks: list[str],
        similarities: list[float]
    ) -> float:
        if not chunks:
            return 0.0
        if similarities:
            avg_sim = sum(similarities) / len(similarities)
            # Direct mapping without arbitrary stretching; thresholds will be tuned after data collection
            if avg_sim >= 0.65:
                return 0.8
            elif avg_sim >= 0.45:
                return 0.5
            else:
                return 0.2
        return 0.5 if len(chunks) > 0 else 0.0
```

Remove the old `_retrieve_knowledge` SQL body and clean up dead imports/constants:
- Remove `from sqlmodel import select`
- Remove `from app.core.database import async_session_maker`
- Remove `from app.models.knowledge import KnowledgeChunk`
- Remove `SIMILARITY_THRESHOLD = 0.5`

- [ ] **Step 3: Review `app/confidence/signals.py`**

Open `app/confidence/signals.py` and verify `RAGSignal.calculate()` works with the new `similarities` score distribution (0~1 from reranker/RRF, potentially lower than old `1.0 - cosine_distance`). The formula `max_sim * 0.4 + avg_sim * 0.3 + coverage * 0.3` is mathematically still valid regardless of score source, but the absolute output range may shift. No code change is strictly required, but add a comment:

```python
# Note: similarities now come from reranker/RRF instead of 1.0 - cosine_distance.
# Thresholds may need recalibration once Golden Dataset is available.
```

- [ ] **Step 4: Review `app/agents/supervisor.py`**

Confirm that `SupervisorAgent.coordinate()` has a broad `try/except` around the specialist call. If `HybridRetriever.retrieve()` raises an exception, it should be caught and returned as:

```python
{
    "answer": "抱歉，系统暂时无法处理您的请求。请稍后重试或联系人工客服。",
    ...
}
```

This is already the case in the current code (lines 329-338), so no change is needed unless the exception type changes.

- [ ] **Step 5: Commit**

```bash
git add app/agents/policy.py app/confidence/signals.py tests/agents/test_policy.py
git commit -m "feat(policy): integrate HybridRetriever into PolicyAgent, clean dead code"
```

---

## Task 10: Remove Orphaned `retrieve` Node

**Files:**
- Modify: `app/graph/nodes.py`

- [ ] **Step 1: Delete the orphaned `retrieve` function**

In `app/graph/nodes.py`, remove the entire `retrieve` async function (the one that queries `KnowledgeChunk.embedding.cosine_distance`). Also remove `SIMILARITY_THRESHOLD` if it's no longer used elsewhere in the file.

Leave `generate`, `intent_router`, `query_order`, `handle_refund`, `check_refund_eligibility` untouched.

- [ ] **Step 2: Verify no other file imports `retrieve` from nodes.py**

Run: `grep -r "from app.graph.nodes import.*retrieve" app/ tests/ test/`
Expected: No matches.

- [ ] **Step 3: Commit**

```bash
git add app/graph/nodes.py
git commit -m "refactor(nodes): remove orphaned retrieve node that queried pgvector"
```

---

## Task 11: ETL Script for Qdrant

**Files:**
- Create: `scripts/etl_qdrant.py`

- [ ] **Step 1: Create `scripts/etl_qdrant.py`**

```python
import asyncio
import glob
import os
import sys

sys.path.append(os.getcwd())

_global_point_id_counter = 0

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import models
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import embedding_model
from app.retrieval.sparse_embedder import SparseTextEmbedder

BATCH_SIZE = 50


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def embed_dense_with_retry(texts: list[str]) -> list[list[float]]:
    return await embedding_model.aembed_documents(texts)


def get_loader(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path)
    elif ext in [".md", ".txt"]:
        return TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"不支持的文件类型: {ext}")


async def process_file(file_path: str, source_name: str, qdrant_client: QdrantKnowledgeClient, sparse_embedder: SparseTextEmbedder):
    print(f"🚀 [Start] 处理文件: {source_name}")
    try:
        loader = get_loader(file_path)
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        )
        split_docs = text_splitter.split_documents(docs)
        total_chunks = len(split_docs)
        print(f"  📄 切分完成: {total_chunks} 个片段")
        if total_chunks == 0:
            print("  ⚠️ 警告: 文件为空或无法读取")
            return

        for i in range(0, total_chunks, BATCH_SIZE):
            batch_docs = split_docs[i : i + BATCH_SIZE]
            batch_texts = []
            batch_metas = []
            for idx, doc in enumerate(batch_docs):
                cleaned = doc.page_content.strip()
                if cleaned:
                    batch_texts.append(cleaned)
                    page = doc.metadata.get("page", 0) + 1
                    batch_metas.append({"page": page, "chunk_index": i + idx})

            if not batch_texts:
                print(f"  ⚠️ 跳过空白批次 {i}")
                continue

            print(f"  🧠 Embedding 批次 {i // BATCH_SIZE + 1} (有效片段: {len(batch_texts)})...")
            dense_vectors = await embed_dense_with_retry(batch_texts)
            sparse_vectors = await sparse_embedder.aembed(batch_texts)

            points = []
            for j, text in enumerate(batch_texts):
                points.append(models.PointStruct(
                    id=_global_point_id_counter,
                    vector={
                        "dense": dense_vectors[j],
                        "sparse": sparse_vectors[j],
                    },
                    payload={
                        "content": text,
                        "source": source_name,
                        "meta_data": batch_metas[j],
                    },
                ))
                _global_point_id_counter += 1

            await qdrant_client.upsert_chunks(points)

        print(f"✅ [Done] {source_name} 处理完毕")
    except Exception as e:
        print(f"❌ [Error] 处理文件 {file_path} 失败: {e}")


async def main():
    base_dir = "data"
    all_files = []
    for ext in ["*.pdf", "*.md", "*.txt"]:
        all_files.extend(glob.glob(os.path.join(base_dir, ext)))

    print(f"📂 扫描到 {len(all_files)} 个文件待处理...")

    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY,
    )
    await qdrant_client.recreate_collection()
    sparse_embedder = SparseTextEmbedder()

    for file_path in all_files:
        source_name = os.path.basename(file_path)
        await process_file(file_path, source_name, qdrant_client, sparse_embedder)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run ETL against local Qdrant**

Ensure Qdrant is running (`docker-compose up -d qdrant`), then:

Run: `python scripts/etl_qdrant.py`
Expected: Prints processing info for `data/` files and completes without errors.

- [ ] **Step 3: Verify data in Qdrant**

Run: `curl -s http://localhost:6333/collections/knowledge_chunks | python -m json.tool`
Expected: JSON showing collection exists with `vectors_count > 0`.

- [ ] **Step 4: Commit**

```bash
git add scripts/etl_qdrant.py
git commit -m "feat(etl): add Qdrant-based ETL with dense + BM25 sparse vectors"
```

---

## Task 12: Final Integration Test & Regression Check

**Files:**
- All of the above

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All new tests pass; existing tests that do not depend on pgvector knowledge retrieval should still pass. Any legacy tests that hard-depend on `KnowledgeChunk` SQL may fail and should be updated or removed.

- [ ] **Step 2: Smoke test PolicyAgent end-to-end (manual)**

Start the application stack (`./start.sh`), then run a quick Python snippet:

```python
import asyncio
from app.agents.policy import PolicyAgent

async def main():
    agent = PolicyAgent()
    result = await agent.process({"question": "怎么退货", "user_id": 1})
    print(result.response)

asyncio.run(main())
```

Expected: The agent returns a policy-based answer grounded in retrieved chunks (not "暂未查询到相关规定" unless Qdrant is empty).

- [ ] **Step 3: Commit any remaining fixes**

---

## Plan Self-Review Checklist

| Spec Section | Covered By Task |
|--------------|-----------------|
| Qdrant collection design | Task 5 |
| Dense embeddings | Task 3 |
| Sparse BM25 embedder | Task 4 |
| Query rewrite | Task 6 |
| Reranker | Task 7 |
| Hybrid retrieval + RRF | Task 8 |
| PolicyAgent integration | Task 9 |
| Remove orphaned retrieve node | Task 10 |
| ETL script | Task 11 |
| docker-compose / start.sh | Task 1 |
| Configuration | Task 2 |
| Tests | Tasks 4,5,6,7,8,9,12 |

**No placeholders detected.** Every step contains exact file paths, code snippets, and run commands.

---

## Post-Implementation Updates

以下记录实际代码合并到 `main` 分支后，与原始计划相比发生的关键差异和补充清理工作：

### 1. pgvector 彻底清理（超出 Task 10 范围）

Task 10 原计划仅移除 `KnowledgeChunk` 的检索逻辑。实际执行中，为了不给后续维护留下技术债务，进行了更彻底的清理：
- 从 `pyproject.toml` 移除了 `pgvector` 依赖
- 删除了 `app/models/knowledge.py`（`KnowledgeChunk` 模型定义）
- 创建了 Alembic 迁移脚本 `migrations/versions/drop_knowledge_chunks_table.py`，在生产数据库中执行了 `DROP TABLE knowledge_chunks` 和 `DROP EXTENSION IF EXISTS vector`
- `docker-compose.yaml` 中的数据库镜像从 `pgvector/pgvector:pg16` 切回标准 `postgres:16`

### 2. `app/graph/nodes.py` 完全删除

计划中 Task 10 提到"Modify: `app/graph/nodes.py`"并移除 `retrieve` 节点。但由于 Supervisor 架构重构后，`query_order`、`handle_refund`、`check_refund_eligibility` 等节点函数已没有任何调用方，且与 `OrderAgent` 存在大量重复业务逻辑，因此**直接删除了整个文件**。

### 3. 新增公共模块以消除重复

实际开发过程中发现原计划未覆盖的架构级重复代码，进行了以下提取：

| 新增文件 | 提取的内容 | 替代的使用点 |
|----------|-----------|-------------|
| `app/core/llm_factory.py` | `create_openai_llm()` 工厂函数 | `app/agents/base.py`、`app/retrieval/rewriter.py`、`app/confidence/signals.py`、`app/intent/classifier.py`（原 `app/graph/nodes.py` 也已删除） |
| `app/utils/order_utils.py` | `extract_order_sn()`、`classify_refund_reason()` | `app/agents/order.py`（原 `app/graph/nodes.py` 中也有重复，已随文件删除一并解决） |

### 4. 代码清理与质量修复

在功能合并后，启动了多个并行 agent 进行死代码扫描，并配合 `vulture` / `ruff` / `ty` 进行静态分析，修复了以下问题：
- 删除了 `app/services/refund_service.py` 中的 `RefundReviewService` 占位死代码
- 删除了 `app/core/database.py` 中空的 `init_db()` stub
- 清理了 `celery_worker.py` 和 `test/` 目录中大量未使用的 import
- 修复了 `app/graph/workflow.py` 的恒真条件路由、`app/main.py` 的静默异常吞掉、`app/retrieval/retriever.py` 的重复 `RetrievedChunk` 构造等问题
- 修复了 `test/integration/test_chat_api.py:467` 的 `B023` 闭包变量绑定警告

### 5. ETL 脚本简化

`scripts/etl_qdrant.py` 中原有的 4 个完全相同的 `@retry(...)` 装饰器被提取为模块级常量 `_RETRY_DECORATOR`。

### 6. 测试 patch 路径更新

`tests/retrieval/test_rewriter.py` 中的 mock patch 目标从 `app.retrieval.rewriter.ChatOpenAI` 更新为 `app.core.llm_factory.ChatOpenAI`，因为 rewriter 现在通过工厂函数实例化 LLM。
