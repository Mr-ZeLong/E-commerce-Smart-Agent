FROM python:3.13-slim

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Install system dependencies for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

RUN chown -R appuser:appgroup /app
USER appuser

# Ensure the virtual environment is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Default command (overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
