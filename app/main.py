"""
Dashboard de estado de jobs ETL - HotBoat
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db.connection import get_connection
from app.tourism_dashboard import build_html as _build_tourism_html


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


app = FastAPI(title="HotBoat ETL Dashboard", docs_url=None, redoc_url=None, lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

JOB_LABELS: Dict[str, str] = {
    "meta_ads_sync":          "Meta Ads (Marketing)",
    "flujo_caja_sync":        "Flujo de Caja",
    "sheets_import":          "Google Sheets",
    "export_reservas_sheets": "Export Reservas → Sheets",
    "booknetic_scrape":       "Booknetic",
}


def _query_jobs() -> List[Dict[str, Any]]:
    sql = """
        SELECT DISTINCT ON (job_name)
            job_name,
            status,
            started_at,
            finished_at,
            row_count,
            error
        FROM job_runs
        ORDER BY job_name, started_at DESC
    """
    rows = []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                for r in cur.fetchall():
                    rows.append(dict(zip(cols, r)))
    except Exception as exc:
        print(f"[dashboard] Error consultando job_runs: {exc}")
    return rows


def _query_history(job_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    sql = """
        SELECT job_name, status, started_at, finished_at, row_count, error
        FROM job_runs
        WHERE job_name = %s
        ORDER BY started_at DESC
        LIMIT %s
    """
    rows = []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (job_name, limit))
                cols = [d[0] for d in cur.description]
                for r in cur.fetchall():
                    rows.append(dict(zip(cols, r)))
    except Exception as exc:
        print(f"[dashboard] Error consultando historial: {exc}")
    return rows


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@app.get("/", response_class=HTMLResponse)
def index():
    html = (STATIC_DIR / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/status")
def api_status():
    rows = _query_jobs()
    jobs = []
    for r in rows:
        s = _serialize(r)
        s["label"] = JOB_LABELS.get(s["job_name"], s["job_name"])
        jobs.append(s)
    # Incluir jobs conocidos aunque no hayan corrido nunca
    known = set(r["job_name"] for r in rows)
    for name, label in JOB_LABELS.items():
        if name not in known:
            jobs.append({"job_name": name, "label": label, "status": None,
                         "started_at": None, "finished_at": None,
                         "row_count": None, "error": None})
    return JSONResponse({"jobs": jobs})


@app.get("/api/history/{job_name}")
def api_history(job_name: str, limit: int = 20):
    rows = [_serialize(r) for r in _query_history(job_name, limit)]
    return JSONResponse({"job_name": job_name, "runs": rows})


@app.get("/turismo", response_class=HTMLResponse)
def turismo():
    """Dashboard de flujo turístico Pucón — datos en tiempo real desde la DB."""
    try:
        with get_connection() as conn:
            html = _build_tourism_html(conn)
        return HTMLResponse(html)
    except Exception as exc:
        return HTMLResponse(
            f"<pre style='color:red;font-family:monospace;padding:2rem'>Error cargando datos:\n{exc}</pre>",
            status_code=500,
        )


@app.get("/health")
def health():
    return {"ok": True}
