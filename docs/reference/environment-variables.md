# 环境变量参考

复制 `.env.example` 为 `.env` 并填写真实值。

## 项目配置

```bash
PROJECT_NAME=E-commerce Smart Agent
API_V1_STR=/api/v1
```

## 数据库

```bash
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_DB=knowledge_base
```

## Redis

本地 docker-compose 默认密码为 `devpassword`。

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=devpassword
```

## Qdrant

```bash
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=knowledge_chunks
```

## Reranker / Rewriter

可选，不填时使用默认值。

```bash
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1
RERANK_MODEL=qwen3-rerank
REWRITE_MODEL=qwen-turbo
RERANK_TIMEOUT=10.0
REWRITE_TIMEOUT=5.0
REWRITE_CACHE_TTL_SECONDS=3600
```

## LLM

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
DASHSCOPE_API_KEY=...
```

## LLM 模型配置

可选，不填时使用默认值。

```bash
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
```

## LangSmith / LangChain tracing

可选，不填时使用默认值。

```bash
LANGCHAIN_TRACING_V2=False
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=ecommerce-smart-agent
LANGSMITH_OTEL_ENABLED=False
```

## Retriever

可选，不填时使用默认值。

```bash
RETRIEVER_DENSE_TOPK=15
RETRIEVER_SPARSE_TOPK=15
RETRIEVER_RRF_K=60
RETRIEVER_FINAL_TOPK=5
RETRIEVER_MULTI_QUERY=False
RETRIEVER_MULTI_QUERY_N=3
```

## Confidence

可选，不填时使用默认值。

```bash
CONFIDENCE__THRESHOLD=0.7
CONFIDENCE__HIGH_THRESHOLD=0.8
CONFIDENCE__MEDIUM_THRESHOLD=0.5
CONFIDENCE__LOW_THRESHOLD=0.3
CONFIDENCE__RAG_WEIGHT=0.3
CONFIDENCE__LLM_WEIGHT=0.5
CONFIDENCE__EMOTION_WEIGHT=0.2
CONFIDENCE__EVALUATION_MODEL=qwen-turbo
```

## Celery

```bash
CELERY_BROKER_URL=redis://:devpassword@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:devpassword@localhost:6379/0
```

## 安全

```bash
SECRET_KEY=...                    # openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

## WebSocket

可选，不填时使用默认值。

```bash
WEBSOCKET_HEARTBEAT_INTERVAL=30
WEBSOCKET_RECONNECT_TIMEOUT=60
```

## 退款规则与风控阈值

可选，不填时使用默认值。

```bash
HIGH_RISK_REFUND_AMOUNT=2000.0
MEDIUM_RISK_REFUND_AMOUNT=500.0
REFUND_DEADLINE_DAYS=7
```

## 其他

```bash
ENABLE_OPENAPI_DOCS=True
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
KNOWLEDGE_UPLOAD_DIR=uploads/knowledge
OTEL_EXPORTER_OTLP_ENDPOINT=
```

> 更多可选配置（如 SMTP、告警阈值、Graph 路由限制等）请参考 `.env.example`。
