#!/usr/bin/env bash
# PM2 entrypoint — free port 8000, then start FastAPI with project venv only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"
PY="$("$ROOT/scripts/resolve-python.sh")"

free_port() {
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti :"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

# Drop stale uvicorn listeners before binding.
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
free_port

for _ in {1..15}; do
  if ! lsof -i :"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

if lsof -i :"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: Port ${PORT} is still in use. Run: bash $ROOT/scripts/pm2-stop.sh" >&2
  exit 1
fi

export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

echo "Starting API with $PY on port ${PORT}"
exec "$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
