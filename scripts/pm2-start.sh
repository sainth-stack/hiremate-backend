#!/usr/bin/env bash
# Stop existing PM2 apps + stray processes, free port 8000, then start ecosystem.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Stopping existing hiremate PM2 apps (if any)..."
pm2 delete ecosystem.config.cjs 2>/dev/null || pm2 stop ecosystem.config.cjs 2>/dev/null || true

echo "Stopping stray backend processes..."
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
pkill -f 'celery -A backend.celery.app' 2>/dev/null || true

PORT=8000
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti :"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then
    kill -9 $PIDS 2>/dev/null || true
  fi
fi

for _ in {1..10}; do
  if ! lsof -i :"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

echo "Starting PM2 ecosystem..."
pm2 start ecosystem.config.cjs
pm2 save

echo ""
pm2 status
echo ""
echo "API health: curl http://127.0.0.1:8000/health"
