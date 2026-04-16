# 开发指南

## 环境要求

- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- Redis 7+
- Qdrant 1.16+

## 本地开发环境搭建

### 1. 克隆仓库并安装依赖

```bash
# 安装 Python 依赖
uv sync

# 安装前端依赖
cd frontend && npm install
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env`，并填写必要的密钥：

```bash
cp .env.example .env
```

关键变量：
- `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_HOST`, `REDIS_PORT`
- `QDRANT_URL`
- `OPENAI_API_KEY` 或 `DASHSCOPE_API_KEY`
- `SECRET_KEY`

### 3. 初始化数据库

```bash
uv run alembic upgrade head
```

### 4. 启动服务

**方式一：一键启动**
```bash
./start.sh
```

**方式二：手动启动**
```bash
# 终端 1：后端
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：Celery Worker
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo --beat

# 终端 3：前端
cd frontend && npm run dev
```

## 代码规范

- **Python**: `ruff` 负责格式化与 lint，`ty` 负责类型检查
- **TypeScript**: 前端使用 strict mode，通过 `npm run build` 进行类型检查

## 运行测试

```bash
# 后端测试
uv run pytest

# 带覆盖率
uv run pytest --cov=app --cov-fail-under=75

# 前端构建验证
cd frontend && npm run build

# E2E 测试
cd frontend && npm run test:e2e
```

## 调试技巧

- 后端 API 文档默认在 `/docs`（开发环境）
- LangGraph 执行日志可在 `app/observability/` 中配置 OpenTelemetry 导出
- 管理员后台地址：`http://localhost:5173/admin.html`
- 用户端地址：`http://localhost:5173/`
