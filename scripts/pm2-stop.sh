#!/usr/bin/env bash
# Stop HireMate PM2 apps and kill stray backend/frontend processes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Stopping PM2 apps (user: $(whoami))..."
pm2 delete all 2>/dev/null || true

echo "==> Stopping stray HireMate processes..."
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
pkill -f 'celery -A backend.celery.app' 2>/dev/null || true
pkill -f 'vite' 2>/dev/null || true

free_port() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti :"${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

for port in 8000 8001 5173; do
  echo "==> Freeing port ${port}..."
  free_port "$port"
done

sleep 1

echo ""
echo "==> Port check (8000/5173 should be empty):"
ss -ltnp 2>/dev/null | grep -E ':8000|:5173' || echo "  OK — ports free"

echo ""
echo "==> Process check:"
ps aux | grep -E 'uvicorn backend.main|celery -A backend.celery|vite' | grep -v grep || echo "  OK — no stray processes"

pm2 status || true
