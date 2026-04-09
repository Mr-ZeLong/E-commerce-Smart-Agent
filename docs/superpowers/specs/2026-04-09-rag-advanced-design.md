# Advanced RAG 升级设计文档

> 将项目 RAG 从基础向量检索（Naive RAG）升级为基于 Qdrant 的混合检索 + 查询改写 + 重排序（Advanced RAG）。

---

## 1. 背景与目标

### 1.1 当前现状
项目现有 RAG 实现是一个**功能完整的 Naive RAG**：
- 使用 `RecursiveCharacterTextSplitter` 切分文档
- 使用 `text-embedding-v3`（1024 维）生成 dense embedding
- 使用 **PostgreSQL + pgvector + HNSW** 做向量检索（`top_k=5`，cosine distance，硬阈值 `distance < 0.5`）
- `PolicyAgent` 直接执行 SQL 查询并拼接结果给 LLM

### 1.2 目标
升级到 **2025-2026 年企业智能客服的主流 Advanced RAG 基线**，实现：
1. **混合检索（Hybrid Search）**：dense 语义检索 + sparse 关键词检索（BM25）
2. **查询改写（Query Rewriting）**：用轻量 LLM 将用户口语化问题改写为更适合文档检索的正式 query
3. **重排序（Re-ranking）**：使用 `qwen3-rerank` 对召回结果进行精排
4. **向量数据库迁移**：将知识库向量数据从 pgvector 迁移到 **Qdrant 1.16.3**

---

## 2. 总体架构

### 2.1 架构决策
在 `app/` 下新建 **`app/retrieval/`** 子模块，作为 RAG 检索层的统一抽象。`PolicyAgent` 不再直接操作任何向量数据库，而是调用 `retrieval` 模块的接口。

### 2.2 目录结构变更
```
app/
├── retrieval/
│   ├── __init__.py
│   ├── client.py          # QdrantAsyncClient 封装
│   ├── embeddings.py      # 迁移现有的 QwenEmbeddings（dense）
│   ├── sparse_embedder.py # FastEmbed BM25 sparse encoder
│   ├── rewriter.py        # qwen-flash 查询改写
│   ├── retriever.py       # HybridRetriever（dense+sparse+RRF）
│   └── reranker.py        # qwen3-rerank 封装
scripts/
├── etl_qdrant.py          # 新的 ETL：生成 dense+sparse，写入 Qdrant
app/agents/
├── policy.py              # 修改 _retrieve_knowledge + _estimate_confidence
app/core/
├── config.py              # 新增 Qdrant、reranker、rewrite 配置
```

### 2.3 保留与废弃
- **保留**：PostgreSQL 继续用于 `orders`、`refund_applications`、`audit_logs` 等业务表
- **废弃**：`scripts/etl_policy.py` 被 `etl_qdrant.py` 取代
- **兼容**：`app/models/knowledge.py` 中的 `KnowledgeChunk` 表定义保留，避免破坏 alembic 历史和其他引用，但**不再用于检索**

---

## 3. 外部依赖

### 3.1 新增 Python 依赖
```toml
qdrant-client = ">=1.16.0,<1.17.0"
fastembed = ">=0.6.0"
```

> **版本说明**：`qdrant-client` 与服务端 `1.16.3` 保持同主/次版本，确保 `prefetch + fusion` API 行为一致。

### 3.2 新增基础设施
- **Qdrant 1.16.3**：通过 `docker-compose.yaml` 部署
- **fastembed 模型下载**：首次运行时会从 HuggingFace 自动下载 `Qdrant/bm25` 模型（约几十 MB），生产环境需配置模型缓存目录或离线加载

---

## 4. 数据模型与存储

### 4.1 Qdrant Collection 设计
- **Collection name**: `knowledge_chunks`
- **Dense vector**: `dense`
  - `size`: 1024
  - `distance`: Cosine
  - `hnsw_config`: 默认
- **Sparse vector**: `sparse`
  - `SparseVectorParams(modifier=Modifier.IDF)`
  - Qdrant 服务端自动维护 IDF
- **Payload**:
  - `content`: str — chunk 文本
  - `source`: str — 来源文件名
  - `meta_data`: dict — `{"page": int, "chunk_index": int}`

### 4.2 Qdrant Client 接口（`app/retrieval/client.py`）
```python
class QdrantKnowledgeClient:
    def __init__(self, url: str, collection_name: str, api_key: str | None = None): ...

    async def ensure_collection(self) -> None:
        """幂等创建 collection，配置 dense + sparse"""

    async def upsert_chunks(self, points: list[models.PointStruct]) -> None:
        """批量写入 chunk 向量与 payload"""

    async def query_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        dense_limit: int = 15,
        sparse_limit: int = 15,
    ) -> list[models.ScoredPoint]:
        """
        使用 Qdrant 的 prefetch + fusion API（通过 query_points）。
        qdrant-client >=1.16 的 AsyncQdrantClient 已移除 search 方法，必须使用 query_points。
        - prefetch 1: dense search (limit=dense_limit)
        - prefetch 2: sparse search (limit=sparse_limit)
        - query: fusion=RRF (由 Qdrant 服务端计算)
        返回 response.points（list[ScoredPoint]）
        """
```

---

## 5. 数据流

### 5.1 ETL 数据流（`scripts/etl_qdrant.py`）

**Step 1: 文档加载与切分**
- 扫描 `data/` 目录（`*.pdf`, `*.md`, `*.txt`）
- `PyPDFLoader` / `TextLoader` 加载
- `RecursiveCharacterTextSplitter(chunk_size=500, overlap=50)` 切分
- 清洗：`.strip()`，过滤空字符串

**Step 2: 向量生成（批量，batch_size=50）**
- **Dense**: `QwenEmbeddings.aembed_documents(texts)` → `text-embedding-v3`, 1024 维
- **Sparse**: `fastembed.SparseTextEmbedding("Qdrant/bm25").embed(texts)` → 同步 `Iterator[SparseEmbedding]`
  - **必须添加转换层 + 异步包装**：
    1. 使用 `asyncio.to_thread()` 执行同步生成器，避免阻塞事件循环
    2. 将 `fastembed.SparseEmbedding` 解包为 `qdrant_client.models.SparseVector(indices, values)`

**Step 3: 写入 Qdrant**
- `recreate_collection` 幂等重建（知识库当前数据量极小，全量重建最干净）
- `upsert` 每个 point 包含 `vector={"dense": ..., "sparse": ...}` 和 payload

### 5.2 查询数据流（`PolicyAgent.process`）

```
用户问题
  │
  ▼
[rewrite_query]  ──► qwen-flash（非思考模式）改写/扩展查询
  │                     失败时回退到原始查询
  ▼
[hybrid_retrieve] ──► Qdrant dense 召回 Top-15
                    ──► Qdrant sparse 召回 Top-15
                    ──► Qdrant RRF 融合（k=60）→ Top-15 候选
  │
  ▼
[rerank] ──► qwen3-rerank 精排 Top-15 → 取 Top-5
  │             失败时跳过，直接返回 RRF Top-5
  ▼
[generate] ──► PolicyAgent 调用 LLM 生成回答
```

**RRF 公式**（Qdrant 服务端计算）：
```python
score = Σ 1 / (k + rank_i)   # k = 60
```
其中 `rank_i` 是该文档在第 i 路召回中的排名（从 1 开始）。

### 5.3 Query Rewriting Prompt
```
你是一个电商客服查询优化专家。请将用户的口语化问题改写成一个更适合文档检索的查询。
要求：
1. 消除口语歧义，使用更正式、更具体的表达
2. 保留原意，不要添加文档中没有的信息
3. 只返回改写后的查询文本，不要解释

用户问题：{question}
改写后的查询：
```

---

## 6. 模块接口设计

### 6.1 `app/retrieval/retriever.py`
```python
@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float
    metadata: dict | None = None

class HybridRetriever:
    def __init__(
        self,
        qdrant_client: QdrantKnowledgeClient,
        dense_embedder: QwenEmbeddings,
        sparse_embedder: SparseTextEmbedder,
        reranker: QwenReranker,
        rewriter: QueryRewriter,
    ):
        ...

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """完整检索流程：改写 → dense+sparse 召回 → RRF → rerank"""
        # 实现要点：
        # 1. rewriter.rewrite(query) 返回单条 query（若返回多行，取第一行非空文本）
        # 2. qdrant_client.query_hybrid(...) 使用 query_points API
        # 3. reranker.rerank(...) 对候选文档做截断后传入
```

### 6.2 `app/retrieval/reranker.py`
```python
class QwenReranker:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "qwen3-rerank",
        timeout: float = 10.0,
        max_document_chars: int = 12000,  # 约 4000 token 的字符安全边际
    ): ...

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankResult]:
        """
        调用阿里云百炼原生 Rerank API（endpoint: /compatible-api/v1/reranks）。
        注意：这不是 OpenAI 官方 rerank 规范，请求/响应格式有差异。
        实现前必须先用 curl 验证实际响应结构（常见字段：index / document_index, relevance_score / score）。
        传入 document 前先做字符截断（max_document_chars），避免触发服务端长度限制。
        返回：list[(original_index, relevance_score)]，按 score 降序排列
        """
```

### 6.3 `app/retrieval/rewriter.py`
```python
class QueryRewriter:
    def __init__(self, base_url: str, api_key: str, model: str = "qwen-turbo", timeout: float = 5.0): ...

    async def rewrite(self, query: str) -> str:
        """
        调用 qwen-turbo（或经确认可用的轻量模型）改写查询。
        解析策略：取返回文本的第一行非空内容作为改写结果；
        若解析为空或调用失败，回退到原始 query。
        """
```

### 6.4 `app/retrieval/sparse_embedder.py`
```python
class SparseTextEmbedder:
    def __init__(self, model_name: str = "Qdrant/bm25"): ...

    async def aembed(self, texts: list[str]) -> list[models.SparseVector]:
        """
        使用 fastembed 将文本异步编码为 BM25 sparse vectors。
        内部转换逻辑：
        1. 在 `asyncio.to_thread()` 中执行 `fastembed.SparseTextEmbedding.embed(texts)`
        2. `list()` 化同步生成器，得到 `list[SparseEmbedding]`
        3. 对每个 SparseEmbedding 提取 .indices 和 .values
        4. 封装为 `qdrant_client.models.SparseVector(indices=..., values=...)`
        懒加载模型，首次调用时初始化。
        """
```

### 6.5 `app/agents/policy.py` 变更
`PolicyAgent._retrieve_knowledge()` 从直接查 pgvector，改为：
```python
from app.retrieval import get_retriever

async def _retrieve_knowledge(self, question: str) -> tuple[list[str], list[float], list[str]]:
    retriever = get_retriever()
    results = await retriever.retrieve(question)
    chunks = [r.content for r in results]
    similarities = [r.score for r in results]
    sources = [r.source for r in results]
    return chunks, similarities, sources
```

`PolicyAgent._estimate_confidence()` 同步修改：
- 旧逻辑依据 `avg_similarity >= 0.7 / 0.5` 分段映射
- 新架构下 `similarities` 来自 reranker score（0~1，但分布更"挑剔"）
- **修改方案**：暂时移除硬编码的 `0.7/0.5` 分段，改为直接使用 `avg(score)` 作为初步置信度估计，待 Golden Dataset 验证后再优化映射策略

### 6.6 `app/graph/nodes.py` 变更
`retrieve` 节点当前仍直接查询 `KnowledgeChunk`（pgvector）。为避免新旧检索双轨运行：
- **将 `retrieve` 节点改为调用 `app.retrieval.get_retriever()`**，与 `PolicyAgent` 共用同一检索层
- `embedding_model` 的声明可迁移到 `app.retrieval.embeddings`，`nodes.py` 改为从该模块导入

---

## 7. 配置参数

新增 `app/core/config.py` 字段：

```python
# Qdrant
QDRANT_URL: str = "http://localhost:6333"
QDRANT_API_KEY: str | None = None
QDRANT_COLLECTION_NAME: str = "knowledge_chunks"
QDRANT_TIMEOUT: float = 10.0
QDRANT_RETRIES: int = 3

# 模型配置
RERANK_MODEL: str = "qwen3-rerank"
REWRITE_MODEL: str = "qwen-turbo"
RERANK_TIMEOUT: float = 10.0
REWRITE_TIMEOUT: float = 5.0

# 检索参数
RETRIEVER_DENSE_TOPK: int = 15
RETRIEVER_SPARSE_TOPK: int = 15
RETRIEVER_RRF_K: int = 60
RETRIEVER_FINAL_TOPK: int = 5

# fastembed 缓存
FASTEMBED_CACHE_PATH: str | None = None
```

---

## 8. docker-compose.yaml 变更

新增 Qdrant 服务：

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

同时 `volumes` 末尾新增：
```yaml
volumes:
  postgres_data:
  qdrant_storage:
```

**PostgreSQL（db 服务）保持不变**，继续承载业务数据。

---

## 9. 错误处理与降级策略

| 故障场景 | 处理策略 |
|---------|---------|
| Qdrant 连接失败 | `HybridRetriever.retrieve()` 捕获异常，记录日志，整体失败，返回系统错误提示（由 Supervisor 包装为友好回复）。 |
| sparse embedder 加载失败 / ONNX Runtime 崩溃 | 跳过 sparse，仅使用 dense 向量执行 Qdrant 检索，保证服务可用。 |
| qwen3-rerank 超时/失败 | 跳过 rerank，直接返回 RRF 融合后的 Top-5。 |
| qwen-flash 改写失败 | 回退到原始查询继续检索。 |
| dense embedder 失败 | 整体失败，返回"系统暂时无法处理"。 |
| RRF 后结果为空 | `chunks=[]`，正常传给 LLM，由 Prompt 约束回答"抱歉，暂未查询到相关规定"。 |

---

## 10. 测试策略

### 10.1 单元测试（`tests/retrieval/`）
- `test_rewriter.py`：mock LLM，测试改写成功 / 失败回退
- `test_reranker.py`：mock qwen3-rerank API，验证排序结果映射
- `test_retriever.py`：mock Qdrant client，验证 dense + sparse + RRF + rerank 调用链
- `test_client.py`：验证 collection 创建参数和 upsert 行为
- `test_sparse_embedder.py`：验证 fastembed `SparseEmbedding` → Qdrant `SparseVector` 转换

### 10.2 集成测试
- `docker-compose.yaml` 启动本地 Qdrant
- `scripts/etl_qdrant.py` 导入测试文档
- 端到端验证：给定查询，返回合理 chunks，rerank 后顺序改善
- 对比验证：pure dense vs hybrid 的 Recall@K

### 10.3 回归测试
- `tests/agents/test_policy.py`：更新 mock 方式，改为 mock `HybridRetriever.retrieve()`

> **注意**：所有新增/更新的测试统一放入 `tests/` 目录，与项目现有 `tests/` 结构保持一致。

---

## 11. 风险与后续迭代

### 11.1 RAGSignal 置信度兼容性问题
当前 `RAGSignal` 基于 `1.0 - cosine_distance` 计算置信度，范围大致在 **0.5 ~ 1.0**。`qwen3-rerank` 返回的 `relevance_score` 虽然也是 0-1，但分布可能更"挑剔"（高分需要更强的语义匹配）。

**影响**：reranker score 整体偏低时，`RAGSignal` 分数可能下降，触发不必要的人工接管。

**缓解措施（上线安全网）**：
1. **上线初期**：直接降低 `CONFIDENCE.THRESHOLD`（如从 0.7 临时调至 0.55），并基于 `RetrievedChunk.score`（reranker score 或 RRF score）重新设定 `PolicyAgent._estimate_confidence()` 的分段阈值。避免无意义的线性拉伸（如 `0.5 + score * 0.5` 会扭曲真实分布）。
2. **并行埋点**：收集真实 score 分布数据（min/max/avg/percentile）。
3. **数据充足后**：基于 Golden Dataset 重新校准 `CONFIDENCE.THRESHOLD` 和 `_estimate_confidence()` 分段逻辑，恢复为数据驱动的阈值。

`PolicyAgent._estimate_confidence()` 同步移除旧硬编码的 `0.7/0.5` 分段，改为基于新 score 分布的临时阈值。

### 11.2 中文 BM25 效果的不确定性
`fastembed` 的 `Qdrant/bm25` 底层使用 Snowball stemmer，主要对英文优化。中文没有 stemming，其 tokenizer 对中文字词的切分效果有待验证。

**影响**：sparse retrieval 在中文政策文档上的召回效果可能不及预期。

**缓解措施**：
- 第一阶段先用 `Qdrant/bm25` 跑通架构
- 在开发第二周前完成 **Golden Dataset**（至少 50 条中文政策查询），对比 **pure dense** vs **hybrid** 的 Recall@K
- 若效果不佳，后续可替换为自定义 `jieba` 分词 + 手动构建 sparse vector

### 11.3 fastembed 的依赖与模型下载
`fastembed` 依赖 `onnxruntime`，首次初始化时会从 HuggingFace 下载模型文件。

**影响**：
- 离线环境可能下载失败
- ARM 架构（Apple Silicon、华为鲲鹏、AWS Graviton 等）可能需要 `onnxruntime-gpu` 或自行编译，Linux ARM64 尤其需要注意

**缓解措施**：
- 实现中使用**懒加载**（lazy init），避免服务启动时阻塞
- 通过 `FASTEMBED_CACHE_PATH` 配置模型缓存目录
- 生产环境 CI/CD 预先将模型文件放入容器镜像的缓存目录
- 在 README / 部署文档中补充 ARM 环境的处理方案

### 11.4 qwen3-rerank API 返回格式待验证
阿里云文档仅提供请求示例，未给出完整响应体 schema。OpenAI-compatible rerank API 的标准返回通常为：
```json
{"results": [{"index": 0, "relevance_score": 0.95}]}
```
但字段名需实际调用后确认。

**缓解措施**：
- `QwenReranker` 实现时预留灵活的解析逻辑，覆盖多种常见字段名（`index`/`document_index`，`relevance_score`/`score`）
- 解析失败时降级为恒等排序（按输入顺序）
- **实现前先用 `curl`/Python 脚本实际调用验证响应格式**，并将验证结果记录到 PR 描述中

---

## 12. 变更清单

### 新增文件
1. `app/retrieval/__init__.py`
2. `app/retrieval/client.py`
3. `app/retrieval/embeddings.py`（从 `app/graph/nodes.py` 迁移 `QwenEmbeddings`）
4. `app/retrieval/sparse_embedder.py`
5. `app/retrieval/rewriter.py`
6. `app/retrieval/retriever.py`
7. `app/retrieval/reranker.py`
8. `scripts/etl_qdrant.py`
9. `tests/retrieval/test_client.py`
10. `tests/retrieval/test_retriever.py`
11. `tests/retrieval/test_rewriter.py`
12. `tests/retrieval/test_reranker.py`
13. `tests/retrieval/test_sparse_embedder.py`

### 修改文件
1. `app/agents/policy.py` — 替换 `_retrieve_knowledge` + 修改 `_estimate_confidence`
2. `app/graph/nodes.py` — `retrieve` 节点改为调用 `app.retrieval.get_retriever()`；`embedding_model` 改为从 `app.retrieval.embeddings` 导入
3. `app/confidence/signals.py` — 审查 `RAGSignal` 对新 score 分布的兼容性，必要时调整权重或阈值
4. `app/agents/supervisor.py` — 确认 `HybridRetriever` 异常被正确捕获并包装为友好提示
5. `app/core/config.py` — 新增 Qdrant、reranker、rewriter、fastembed 配置项
6. `docker-compose.yaml` — 新增 qdrant 服务与 volume
7. `pyproject.toml` — 新增 `qdrant-client`、`fastembed` 依赖
8. `tests/agents/test_policy.py` — 更新 mock 方式
9. `.env` / `.env.example` — 新增配置项示例
10. `README.md` / 部署文档 — 更新 Qdrant 部署和 fastembed 缓存说明
11. `start.sh` — 检查是否需要等待 Qdrant healthy

### 废弃（保留但不再使用）
- `scripts/etl_policy.py`
- `app/models/knowledge.py` 中的 `KnowledgeChunk` 用于检索的逻辑
