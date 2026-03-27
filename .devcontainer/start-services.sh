#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/workspaces/FATEC-API-6-SEMESTRE"
LOG_DIR="$ROOT_DIR/.devcontainer/logs"
API_LOG="$LOG_DIR/api.log"
WORKER_LOG="$LOG_DIR/worker.log"

mkdir -p "$LOG_DIR"

cd "$ROOT_DIR/backend"

# Ensures dependencies exist if the volume was recreated.
if [[ ! -x .venv/bin/python ]]; then
  uv sync --frozen
fi

cd "$ROOT_DIR"

if ! pgrep -f "uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload" >/dev/null; then
  nohup env PYTHONPATH=. uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload >"$API_LOG" 2>&1 &
fi

if ! pgrep -f "celery -A backend.tasks.celery_app worker --loglevel=info" >/dev/null; then
  nohup env PYTHONPATH=. uv run celery -A backend.tasks.celery_app worker --loglevel=info >"$WORKER_LOG" 2>&1 &
fi
