# 部署指南

## Docker Compose 部署（推荐）

项目已提供 `docker-compose.yaml`，可直接启动完整环境：

```bash
docker compose up --build
```

包含的服务：
- `app` — FastAPI 主应用
- `worker` — Celery 异步任务 worker
- `postgres` — PostgreSQL 数据库
- `redis` — Redis 缓存与消息队列
- `qdrant` — Qdrant 向量数据库

## 纯 Docker 部署

若使用自定义编排，需确保镜像构建时包含以下文件：

```dockerfile
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY start.sh ./
COPY start_worker.sh ./
COPY migrations/ ./migrations/
COPY data/ ./data/
COPY alembic.ini ./
```

启动命令：

```bash
# 主应用
./start.sh

# Worker
./start_worker.sh
```

## Kubernetes 部署要点

1. **ConfigMap/Secret**: 将 `.env` 中的配置注入为环境变量
2. **PersistentVolume**: PostgreSQL 与 Qdrant 需要持久化存储
3. **Service**: 暴露 FastAPI 的 8000 端口
4. **HPA**: 根据 CPU/内存自动扩缩容 `app` 与 `worker`
5. **Ingress**: 配置域名与 HTTPS 证书

## 环境检查清单

- [ ] `SECRET_KEY` 长度 ≥ 32 字节
- [ ] `ENABLE_OPENAPI_DOCS=False`（生产环境）
- [ ] `CORS_ORIGINS` 配置为实际域名（禁止 `*` + `allow_credentials=True`）
- [ ] PostgreSQL、Redis、Qdrant 可正常连接
- [ ] `OPENAI_API_KEY` 或 `DASHSCOPE_API_KEY` 已配置且余额充足

> 完整环境变量说明请参考 [环境变量参考](../reference/environment-variables.md)。
