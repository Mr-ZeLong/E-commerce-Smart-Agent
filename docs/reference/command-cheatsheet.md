# 常用命令速查表

## 一键启动

```bash
./start.sh
```

## 后端开发

```bash
# 安装依赖
uv sync

# 数据库迁移
uv run alembic upgrade head

# 启动 FastAPI
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Celery Worker（含 Beat）
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo --beat
```

## 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 测试

```bash
# 后端测试
uv run pytest
uv run pytest --cov=app --cov-fail-under=75

# 前端构建验证
cd frontend && npm run build

# 前端 E2E 测试
cd frontend && npm run test:e2e
```

## 代码质量

```bash
# 安装 pre-commit hook
pre-commit install

# 手动检查
uv run ruff check app tests --fix
uv run ruff format app tests
uv run ty check --error-on-warning app tests

# 前端检查
cd frontend && npm run lint && npm run format
```

## 数据库

```bash
# 生成迁移
uv run alembic revision --autogenerate -m "description"

# 执行迁移
uv run alembic upgrade head
```

## 健康检查

```bash
# API
curl http://localhost:8000/health

# Celery Worker
uv run celery -A app.celery_app inspect ping
```
