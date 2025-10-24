#!/usr/bin/env bash
set -euo pipefail

# Ensure working dir is repo root
cd "$(dirname "$0")"

# Prefer venv python if available (Nixpacks usually creates /opt/venv)
if [ -x "/opt/venv/bin/python" ]; then
  export PATH="/opt/venv/bin:$PATH"
fi

exec python -m jobs.runner


