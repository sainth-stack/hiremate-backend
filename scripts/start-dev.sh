#!/usr/bin/env bash
# Restart API + Celery (stop existing dev processes, then start fresh).
# Usage: ./scripts/start-dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PY="$ROOT/backend/.venv/bin/python"
elif [[ -x "$ROOT/venv/bin/python" ]]; then
  PY="$ROOT/venv/bin/python"
else
  PY="python3"
fi

stop_existing() {
  echo "Stopping existing dev processes (if any)..."
  pkill -f 'uvicorn backend.main' 2>/dev/null || true
  pkill -f 'celery -A backend.celery.app' 2>/dev/null || true
  # Ensure port 8001 is free before starting (max ~5s)
  for _ in {1..10}; do
    if ! lsof -i :8001 -sTCP:LISTEN >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
}

wait_for_health() {
  for _ in {1..20}; do
    if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

echo "Using Python: $PY"
echo "PYTHONPATH=$PYTHONPATH"

stop_existing
mkdir -p "$ROOT/logs"

: > "$ROOT/logs/api.log"
: > "$ROOT/logs/celery-ingest.log"
: > "$ROOT/logs/celery-beat.log"

"$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 \
  >> "$ROOT/logs/api.log" 2>&1 &
echo "API pid=$! (logs/api.log)"

"$PY" -m celery -A backend.celery.app worker -Q ingest --concurrency=2 --loglevel=info \
  >> "$ROOT/logs/celery-ingest.log" 2>&1 &
echo "Celery ingest worker pid=$!"

"$PY" -m celery -A backend.celery.app beat --loglevel=info \
  >> "$ROOT/logs/celery-beat.log" 2>&1 &
echo "Celery beat pid=$!"

echo ""
if wait_for_health; then
  echo "Restarted successfully. Health: curl http://127.0.0.1:8001/health"
else
  echo "Started, but health check timed out — see logs/api.log:"
  echo "  tail -f $ROOT/logs/api.log"
fi
