# 运维手册

本文档面向运维工程师，涵盖系统监控、告警排查与常见故障处理。

## 目录

- [服务架构](#服务架构)
- [健康检查](#健康检查)
- [关键指标](#关键指标)
- [日志排查](#日志排查)
- [常见故障](#常见故障)

---

## 服务架构

核心服务及默认端口：

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI | 8000 | 主后端 API |
| Vite (dev) | 5173 | 前端开发服务器 |
| PostgreSQL | 5432 | 主数据库 |
| Redis | 6379 | 缓存、Celery Broker、LangGraph Checkpoint |
| Qdrant | 6333 | 向量数据库 |
| Celery Worker | - | 异步任务执行 |

---

## 健康检查

### API 健康
```bash
curl http://localhost:8000/health
```
期望返回：`{"status":"ok"}`

### 数据库
检查 PostgreSQL 与 Redis 连接：
```bash
uv run python -c "import asyncio; from app.core.database import async_engine; asyncio.run(async_engine.connect())"
```

### Celery Worker
```bash
uv run celery -A app.celery_app inspect ping
```

---

## 关键指标

| 指标 | 来源 | 告警阈值建议 |
|------|------|-------------|
| API P99 延迟 | `/admin/metrics/latency` | > 2000ms |
| 人工转接率 | `/admin/metrics/transfers` | > 30% |
| 平均置信度 | `/admin/metrics/confidence` | < 0.6 |
| CSAT | `/admin/analytics/csat` | < 0.7 |
| 投诉量 | `/admin/analytics/complaint-root-causes` | 单日 > 10 |

---

## 日志排查

- 后端日志级别由 `LOG_LEVEL` 控制（默认 `INFO`）。
- OpenTelemetry trace 可通过 `OTEL_EXPORTER_OTLP_ENDPOINT` 导出到 Jaeger / Tempo。
- Celery 任务失败日志包含任务名与重试次数，定位到 `app/tasks/` 对应模块。

---

## 常见故障

### WebSocket 连接异常
- 检查 Redis 是否正常：`redis-cli ping`
- 确认 `app/main.py` 中 Redis pub/sub 订阅线程已启动
- 查看管理员/用户连接日志中的 `RuntimeError` 提示

### 数据库连接池耗尽
- 增加 `SQLALCHEMY_POOL_SIZE`（默认 10）
- 检查是否存在长时间未提交的事务

### 检索结果为空
- 确认 Qdrant 集合存在：`scripts/etl_qdrant.py`
- 检查 `QDRANT_COLLECTION_NAME` 配置
- 查看知识库文档同步状态：`/admin/knowledge`

### Celery 任务堆积
- 增加 worker 并发数：`--concurrency=8`
- 检查是否有阻塞任务（如 LLM 调用超时）
- 查看 Flower（如部署）监控队列深度

---

## 联系人

- 技术负责人：参见项目 `README.md`
- 紧急通道：生产环境 P1 故障请直接联系值班 SRE
