#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend ci
fi
npm --prefix frontend run build
exec .venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --workers 1 --ws-max-size 8192 --no-access-log
