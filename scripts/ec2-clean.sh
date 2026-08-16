#!/usr/bin/env bash
# Full EC2 cleanup for HireMate — run ON THE SERVER.
#
# Step 1 (as ubuntu):  bash scripts/ec2-clean.sh
# Step 2 (as root):    sudo bash scripts/ec2-clean.sh --root-pm2
#
# Does NOT delete code, venv, .env, or database data.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

clean_user_pm2() {
  echo "=== Cleaning PM2 + processes for user: $(whoami) ==="
  bash "$ROOT/scripts/pm2-stop.sh"
}

clean_root_pm2() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Skip root PM2 cleanup (run with sudo bash scripts/ec2-clean.sh --root-pm2)"
    return 0
  fi
  echo "=== Killing root PM2 daemon ==="
  pm2 kill 2>/dev/null || true
  pkill -f '/root/.pm2' 2>/dev/null || true
  echo "Root PM2 stopped."
}

verify_clean() {
  echo ""
  echo "=== Verification ==="
  echo "Ports:"
  ss -ltnp 2>/dev/null | grep -E ':8000|:5173' || echo "  8000/5173 free"
  echo ""
  echo "Processes:"
  ps aux | grep -E 'uvicorn backend.main|celery -A backend.celery|vite' | grep -v grep || echo "  none"
  echo ""
  echo "PM2 (ubuntu):"
  sudo -u ubuntu pm2 status 2>/dev/null || pm2 status 2>/dev/null || echo "  pm2 not running"
}

case "${1:-}" in
  --root-pm2)
    clean_root_pm2
    ;;
  *)
    clean_user_pm2
    echo ""
    echo "If you ever ran 'sudo pm2', also run:"
    echo "  sudo bash $ROOT/scripts/ec2-clean.sh --root-pm2"
    verify_clean
    ;;
esac
