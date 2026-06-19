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
        import traceback
        tb = traceback.format_exc()
        return HTMLResponse(
            f"<pre style='color:red;background:#1e1e1e;font-family:monospace;padding:2rem'>"
            f"Error cargando dashboard:\n\n{tb}</pre>",
            status_code=500,
        )


@app.get("/turismo/debug")
def turismo_debug():
    """Diagnóstico: verifica conexión DB y existencia de tablas."""
    result: dict = {"db": False, "tables": {}, "row_counts": {}, "error": None}
    try:
        with get_connection() as conn:
            result["db"] = True
            with conn.cursor() as cur:
                for table in ["tourism_signal_snapshots", "pucon_flow_index",
                              "source_query_log", "job_runs"]:
                    cur.execute(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = %s)", (table,)
                    )
                    exists = cur.fetchone()[0]
                    result["tables"][table] = exists
                    if exists:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                        result["row_counts"][table] = cur.fetchone()[0]
    except Exception as exc:
        result["error"] = str(exc)
    return JSONResponse(result)


@app.get("/api/debug/gastos-schema")
def gastos_schema():
    """Devuelve columnas y categorías existentes de la tabla gastos."""
    result: dict = {"columns": [], "categoria_tables": [], "categorias": [], "error": None}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'gastos'
                    ORDER BY ordinal_position
                """)
                result["columns"] = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
                # Buscar tablas de categorías
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name ILIKE '%categor%'
                    ORDER BY table_name
                """)
                cat_tables = [r[0] for r in cur.fetchall()]
                result["categoria_tables"] = cat_tables
                # Leer contenido de cada tabla de categorías
                for tbl in cat_tables:
                    cur.execute(f"SELECT * FROM {tbl} ORDER BY id LIMIT 100")
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                    result["categorias"].append({"table": tbl, "rows": rows})
    except Exception as exc:
        result["error"] = str(exc)
    return JSONResponse(result)


@app.api_route("/api/scan-receipt", methods=["GET", "POST"])
def scan_receipt():
    """Escanea la boleta más reciente de WhatsApp y registra el gasto."""
    import base64
    import json
    import os
    from datetime import date
    import requests as _req

    PHONE_NUMBER  = "56977577307"
    WA_BASE       = "https://hotboat-whatsapp-staging-tom.up.railway.app"
    GASTOS_URL    = f"{WA_BASE}/api/admin/gastos"
    GEMINI_KEY    = os.getenv("GEMINI_API_KEY")
    GEMINI_URL    = (
        "https://generativelanguage.googleapis.com/v1beta/models"
        "/gemini-3.1-flash-lite:generateContent"
    )

    if not GEMINI_KEY:
        return JSONResponse({"ok": False, "error": "GEMINI_API_KEY no configurado en Railway"}, status_code=500)

    # 1. Buscar imagen más reciente en la DB de WhatsApp
    try:
        import psycopg
        wa_db_url = os.getenv("WHATSAPP_DATABASE_URL") or os.getenv("DATABASE_URL")
        with psycopg.connect(wa_db_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT response_text, created_at
                    FROM whatsapp_conversations
                    WHERE phone_number = %s AND message_type = 'image' AND direction = 'incoming'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (PHONE_NUMBER,),
                )
                row = cur.fetchone()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"DB error: {exc}"}, status_code=500)

    if not row:
        return JSONResponse({"ok": False, "error": "No hay imágenes entrantes en la DB"}, status_code=404)

    # 2. Descargar imagen
    img_url = f"{WA_BASE}{row['response_text']}"
    try:
        r = _req.get(img_url, timeout=30)
        r.raise_for_status()
        mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(r.content).decode()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Error descargando imagen: {exc}"}, status_code=500)

    # 3. Analizar con Gemini
    try:
        gemini_resp = _req.post(
            GEMINI_URL,
            params={"key": GEMINI_KEY},
            json={
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": mime, "data": b64}},
                    {"text": (
                        "Analiza esta boleta de Chile. "
                        "Extrae: 1) monto total en CLP (entero), "
                        "2) nombre del comercio, "
                        "3) fecha en formato YYYY-MM-DD (null si no se ve). "
                        'Responde SOLO con JSON: {"monto": 12500, "comercio": "Copec", "fecha": "2024-01-15"}'
                    )},
                ]}],
                "generationConfig": {"maxOutputTokens": 300, "temperature": 0},
            },
            timeout=60,
        )
        gemini_resp.raise_for_status()
        raw_text = (
            gemini_resp.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        extracted = json.loads(clean.strip())
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Gemini error: {exc}", "raw": raw_text if 'raw_text' in dir() else ""}, status_code=500)

    monto    = extracted.get("monto")
    comercio = extracted.get("comercio", "Desconocido")
    fecha    = extracted.get("fecha") or date.today().isoformat()

    if not monto:
        return JSONResponse({"ok": False, "error": "Gemini no pudo extraer el monto", "extracted": extracted}, status_code=422)

    # 4. Registrar gasto
    try:
        gasto_resp = _req.post(
            GASTOS_URL,
            json={"fecha": fecha, "monto": int(monto), "comercio": comercio, "descripcion": "", "notas": "Auto-escaneado desde WhatsApp"},
            timeout=30,
        )
        gasto_resp.raise_for_status()
        gasto_result = gasto_resp.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Error registrando gasto: {exc}"}, status_code=500)

    return JSONResponse({
        "ok": True,
        "comercio": comercio,
        "monto": int(monto),
        "fecha": fecha,
        "imagen_created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        "gasto": gasto_result,
    })


@app.get("/health")
def health():
    return {"ok": True}
