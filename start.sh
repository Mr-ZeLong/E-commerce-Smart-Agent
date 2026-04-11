#!/bin/bash
# 启动所有 v4.1 服务

echo " 启动 E-commerce Smart Agent v4.1 所有服务..."
export PYTHONPATH=$PWD

# 检查依赖
echo " 检查 Python 依赖..."
uv sync

# 检查前端依赖
echo " 检查前端依赖..."
cd frontend && npm install && cd ..

# 构建前端
echo " 构建前端..."
cd frontend && npm run build && cd ..

# 启动 Redis、PostgreSQL 和 Qdrant
echo " 启动基础设施..."
docker compose up -d db redis qdrant

# 等待 Qdrant 就绪
echo "Waiting for Qdrant to be healthy..."
QDRANT_HEALTHY=0
for i in {1..30}; do
  if curl -sf http://localhost:6333/healthz > /dev/null; then
    echo "Qdrant is healthy"
    QDRANT_HEALTHY=1
    break
  fi
  sleep 1
done
if [ "$QDRANT_HEALTHY" -eq 0 ]; then
  echo "Qdrant failed to become healthy"
  exit 1
fi

# 等待数据库就绪
echo " 等待数据库启动..."
sleep 5

# 执行数据库迁移
echo " 执行数据库迁移..."
uv run alembic upgrade head

# 启动服务（使用 tmux 或单独终端）
echo " 启动 FastAPI 服务..."
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

echo " 启动 Celery Worker..."
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo &
CELERY_PID=$!

echo ""
echo " 所有服务已启动！"
echo ""
echo " 访问地址:"
echo "  - FastAPI API: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo "  - 用户界面 (C端): http://localhost:8000/app"
echo "  - 管理员后台 (B端): http://localhost:8000/admin"
echo ""
echo " 前端开发模式 (单独终端运行):"
echo "  cd frontend && npm run dev"
echo ""
echo " 按 Ctrl+C 停止所有服务"

# 等待中断信号
trap "kill $FASTAPI_PID $CELERY_PID; exit" INT
wait