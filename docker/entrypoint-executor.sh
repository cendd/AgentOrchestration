#!/bin/bash
set -e

echo "[EXECUTOR] Starting Agent Orchestrator Executor..."
echo "[EXECUTOR] Max concurrent workers: ${MAX_CONCURRENT:-5}"

exec "$@"
