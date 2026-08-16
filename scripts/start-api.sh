#!/usr/bin/env bash
# PM2 entrypoint — free port 8000, then start FastAPI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"

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

# Drop stale uvicorn listeners (e.g. start-dev.sh or a crashed PM2 worker).
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
free_port

for _ in {1..10}; do
  if ! lsof -i :"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

if [[ -x "$ROOT/backend/.venv/bin/python3" ]]; then
  PY="$ROOT/backend/.venv/bin/python3"
elif [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PY="$ROOT/backend/.venv/bin/python"
else
  PY="python3"
fi

exec "$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
