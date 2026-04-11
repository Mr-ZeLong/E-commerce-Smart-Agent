#!/bin/bash
# 启动 Celery Worker (v4.0)

export PYTHONPATH=$PWD

echo "Waiting for dependencies to be ready..."

# Wait for Redis
REDIS_HEALTHY=0
for i in {1..30}; do
  if nc -z localhost 6379 2>/dev/null; then
    echo "Redis is ready"
    REDIS_HEALTHY=1
    break
  fi
  sleep 1
done
if [ "$REDIS_HEALTHY" -eq 0 ]; then
  echo "Redis failed to become ready"
  exit 1
fi

# Wait for PostgreSQL
PG_HEALTHY=0
for i in {1..30}; do
  if nc -z localhost 5432 2>/dev/null; then
    echo "PostgreSQL is ready"
    PG_HEALTHY=1
    break
  fi
  sleep 1
done
if [ "$PG_HEALTHY" -eq 0 ]; then
  echo "PostgreSQL failed to become ready"
  exit 1
fi

# Wait for Qdrant
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

echo "Starting Celery Worker..."

celery -A app.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --pool=solo \
  -E
