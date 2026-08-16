#!/usr/bin/env bash
# Print absolute path to project venv python. Exit 1 if missing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

candidates=(
  "$ROOT/venv/bin/python3"
  "$ROOT/backend/.venv/bin/python3"
  "$ROOT/venv/bin/python"
  "$ROOT/backend/.venv/bin/python"
)

for candidate in "${candidates[@]}"; do
  if [[ -x "$candidate" ]]; then
    echo "$candidate"
    exit 0
  fi
done

echo "ERROR: Python venv not found under $ROOT" >&2
echo "Fix: cd $ROOT && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
exit 1
