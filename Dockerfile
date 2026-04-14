FROM node:22-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

FROM python:3.13-slim

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Install uv
# Pin uv version for reproducible builds. Update manually after testing.
COPY --from=ghcr.io/astral-sh/uv:0.6.5@sha256:562193a4a9d398f8aedddcb223e583da394ee735de36b5815f8f1d22cb49be15 /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Sync dependencies (no dev packages)
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/
COPY celery_worker.py ./
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY data/ ./data/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN chown -R appuser:appgroup /app
USER appuser

# Ensure the virtual environment is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Default command (overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
