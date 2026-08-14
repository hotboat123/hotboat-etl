#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"

if [ -x "/opt/venv/bin/python" ]; then
  export PATH="/opt/venv/bin:$PATH"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
