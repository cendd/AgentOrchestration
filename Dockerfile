# Multi-stage Dockerfile for Agent Orchestrator
# Build targets: scheduler, executor, sidecar
# Uses uv for fast dependency management

FROM python:3.11-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml .

# Install project dependencies
RUN uv sync --no-dev

# Copy source code
COPY src/ src/

# --- Scheduler target ---
FROM base AS scheduler
COPY docker/entrypoint-scheduler.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ao", "scheduler"]

# --- Executor target ---
FROM base AS executor
COPY docker/entrypoint-executor.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ao", "executor"]

# --- Sidecar target ---
FROM base AS sidecar
COPY docker/entrypoint-sidecar.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ao", "sidecar"]

# --- API server target ---
FROM base AS api
ENTRYPOINT ["uvicorn", "src.api.server:create_app", "--host", "0.0.0.0", "--port", "8000"]
