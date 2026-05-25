#!/bin/bash
set -e

echo "[SCHEDULER] Starting Agent Orchestrator Scheduler..."
echo "[SCHEDULER] Version: $(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || echo 'unknown')"

exec "$@"
