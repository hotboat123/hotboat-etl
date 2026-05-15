#!/usr/bin/env bash
# Arranca jobs runner en background y uvicorn en foreground (exec).
# Con exec, uvicorn es el proceso principal: Railway lo gestiona directamente
# y cuando lo mata no quedan procesos huérfanos en el puerto.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x "/opt/venv/bin/python" ]; then
  export PATH="/opt/venv/bin:$PATH"
fi

echo "[start] Levantando jobs runner en background…"
python -m jobs.runner &

echo "[start] Levantando web server en puerto ${PORT:-8080}…"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
