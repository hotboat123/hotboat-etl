#!/usr/bin/env bash
# Arranca web server (FastAPI/uvicorn) + jobs runner en paralelo.
# Railway inyecta $PORT para el web server; el jobs runner no necesita puerto.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x "/opt/venv/bin/python" ]; then
  export PATH="/opt/venv/bin:$PATH"
fi

echo "[start] Levantando web server en puerto ${PORT:-8080}…"
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1 &
WEB_PID=$!

echo "[start] Levantando jobs runner…"
python -m jobs.runner &
WORKER_PID=$!

# Si cualquiera de los dos muere, Railway reinicia el servicio completo
wait -n "$WEB_PID" "$WORKER_PID"
echo "[start] Proceso terminó — saliendo para forzar reinicio de Railway."
exit 1
