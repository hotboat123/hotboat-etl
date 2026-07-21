"""
HotBoat ETL - proceso worker (jobs en background) + health check para Railway.
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI


def _runner_loop() -> None:
    """Ejecuta jobs.runner.main() y lo reinicia si cae, con backoff."""
    import time
    from db.utils import print_db_identity
    from jobs.runner import main as runner_main

    print_db_identity()   # una sola vez al arrancar el proceso

    delay = 5
    while True:
        try:
            print("[app] Jobs runner iniciando…")
            runner_main()
        except Exception as exc:
            print(f"[app] Jobs runner terminó con error: {exc} — reiniciando en {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 120)
        else:
            break


def _start_jobs_runner() -> None:
    t = threading.Thread(target=_runner_loop, daemon=True, name="jobs-runner")
    t.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_jobs_runner()
    yield


app = FastAPI(title="HotBoat ETL", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}
