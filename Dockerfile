# ===== BUILD STAGE =====
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv
RUN pip install --no-cache-dir uv

# Copy only dependency file first (leverage Docker cache)
COPY pyproject.toml ./

# Install production dependencies only
RUN uv sync --no-dev --no-install-project

# Copy source code
COPY src/ ./src/

# Build the package
RUN uv build --no-sources --out-dir /build/dist


# ===== RUNTIME STAGE =====
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the built wheel - no cache dirs, no dev dependencies
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Copy runtime source files explicitly (not entire /build)
COPY --from=builder /build/src/agent /app/agent
COPY --from=builder /build/src/api /app/api
COPY --from=builder /build/src/cli /app/cli
COPY --from=builder /build/src/common /app/common
COPY --from=builder /build/src/contracts /app/contracts
COPY --from=builder /build/src/orchestrator /app/orchestrator
COPY --from=builder /build/src/sdk /app/sdk
COPY --from=builder /build/src/__init__.py /app/__init__.py

# Verify no cache directories leaked
RUN python -c "\
import os;\
cache_dirs = ['.uv-cache', '__pycache__', '.cache', '.pip'];\
found = [d for d in cache_dirs if any(d in p for p,_,_ in os.walk('/app'))];\
assert not found, f'Cache dirs leaked: {found}';\
print('Verification passed: no cache directories in runtime image')\
"

CMD ["uvicorn", "src.api.server:create_app", "--host", "0.0.0.0", "--port", "8000"]
