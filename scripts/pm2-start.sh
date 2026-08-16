#!/usr/bin/env bash
# Clean start for HireMate on EC2 — run as ubuntu ONLY (not root).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_ROOT="${FRONTEND_ROOT:-/home/ubuntu/hiremate-frontend}"

if [ "$(id -u)" -eq 0 ]; then
  echo "ERROR: Do not run as root." >&2
  echo "Use: su - ubuntu" >&2
  echo "Then: cd $ROOT && bash scripts/pm2-start.sh" >&2
  exit 1
fi

if [ ! -d "$FRONTEND_ROOT" ]; then
  echo "ERROR: Frontend not found at $FRONTEND_ROOT" >&2
  echo "Set FRONTEND_ROOT if your path differs." >&2
  exit 1
fi

PY="$("$ROOT/scripts/resolve-python.sh")"
echo "Using Python: $PY"
"$PY" -m uvicorn --version >/dev/null

cd "$ROOT"
bash "$ROOT/scripts/pm2-stop.sh"

echo ""
echo "==> Starting PM2 ecosystem..."
export FRONTEND_ROOT
pm2 start ecosystem.config.cjs
pm2 save

echo ""
pm2 status

echo ""
echo "Waiting for API health..."
for _ in {1..30}; do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "OK: http://127.0.0.1:8000/health"
    break
  fi
  sleep 1
done

if ! curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
  echo "WARN: API health check failed — run: pm2 logs hiremate-api --lines 40"
fi

if curl -sf "http://127.0.0.1:5173/" >/dev/null 2>&1; then
  echo "OK: http://127.0.0.1:5173/"
else
  echo "WARN: Frontend not responding yet — run: pm2 logs student-frontend --lines 20"
fi
