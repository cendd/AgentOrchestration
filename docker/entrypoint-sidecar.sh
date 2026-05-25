#!/bin/bash
set -e

echo "[SIDECAR] Starting Agent Orchestrator Sidecar..."
echo "[SIDECAR] Monitoring endpoint: ${MONITOR_ENDPOINT:-http://localhost:8000}"

exec "$@"
