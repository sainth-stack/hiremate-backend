#!/usr/bin/env bash
# Start API + Celery ingestion worker (no PM2).
# Usage: ./scripts/start-dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PY="$ROOT/backend/.venv/bin/python"
else
  PY="python3"
fi

echo "Using Python: $PY"
echo "PYTHONPATH=$PYTHONPATH"

mkdir -p "$ROOT/logs"

"$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 \
  > "$ROOT/logs/api.log" 2>&1 &
echo "API pid=$! (logs/api.log)"

"$PY" -m celery -A backend.celery.app worker -Q ingest --concurrency=2 --loglevel=info \
  > "$ROOT/logs/celery-ingest.log" 2>&1 &
echo "Celery ingest worker pid=$!"

"$PY" -m celery -A backend.celery.app beat --loglevel=info \
  > "$ROOT/logs/celery-beat.log" 2>&1 &
echo "Celery beat pid=$!"

echo ""
echo "Started. Health: curl http://127.0.0.1:8001/health"
echo "Stop: pkill -f 'uvicorn backend.main' ; pkill -f 'celery -A backend.celery.app'"
