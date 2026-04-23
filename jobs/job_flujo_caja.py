"""
Importa la hoja "consolidad flujo caja" del spreadsheet Looker HotBoat a PostgreSQL.

Requiere en .env / Railway:
  GOOGLE_SA_JSON_BASE64     Service account de Google (ya configurado)
  LOOKER_SPREADSHEET_ID     ID del spreadsheet "Looker HotBoat"

Opcional:
  FLUJO_CAJA_SHEET_NAME     Nombre exacto de la hoja (default: "consolidad flujo caja")
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from psycopg.types.json import Json

from db.connection import get_connection

SHEET_NAME_DEFAULT = "consolidad flujo caja"


def _get_gspread_client():
    import gspread
    from google.oauth2.service_account import Credentials

    b64 = os.getenv("GOOGLE_SA_JSON_BASE64")
    if not b64:
        raise RuntimeError("GOOGLE_SA_JSON_BASE64 no está definido")
    info = json.loads(base64.b64decode(b64).decode("utf-8"))
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def _row_id(sheet_name: str, row_idx: int, row: Dict[str, Any]) -> str:
    pieces = "|".join(f"{k}={v}" for k, v in sorted(row.items()) if v not in (None, ""))
    raw = f"{sheet_name}||{row_idx}||{pieces}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def run() -> int:
    spreadsheet_id = os.getenv("LOOKER_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError(
            "LOOKER_SPREADSHEET_ID no está definido en .env / Railway"
        )

    sheet_name = os.getenv("FLUJO_CAJA_SHEET_NAME", SHEET_NAME_DEFAULT).strip()

    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)

    # Buscar la hoja ignorando mayúsculas/tildes por si el nombre varía levemente
    ws = None
    for w in sh.worksheets():
        if w.title.strip().lower() == sheet_name.lower():
            ws = w
            break
    if ws is None:
        available = [w.title for w in sh.worksheets()]
        raise RuntimeError(
            f"Hoja '{sheet_name}' no encontrada en el spreadsheet. "
            f"Hojas disponibles: {available}"
        )

    print(f"[flujo_caja] Leyendo hoja '{ws.title}' de spreadsheet {spreadsheet_id}...")
    all_rows = ws.get_all_values()

    if not all_rows:
        print("[flujo_caja] La hoja está vacía, nada que importar")
        return 0

    headers = [str(h).strip() for h in all_rows[0]]
    data_rows = all_rows[1:]
    print(f"[flujo_caja] {len(data_rows)} filas de datos, {len(headers)} columnas")

    rows_to_insert: List[Dict[str, Any]] = []
    for idx, row in enumerate(data_rows, start=2):
        record: Dict[str, Any] = {}
        for col_idx, header in enumerate(headers):
            value = row[col_idx] if col_idx < len(row) else ""
            record[header] = value.strip() if isinstance(value, str) else value

        # Omitir filas completamente vacías
        if not any(v for v in record.values()):
            continue

        rows_to_insert.append({
            "id": _row_id(ws.title, idx, record),
            "fila": idx,
            "raw": record,
        })

    print(f"[flujo_caja] {len(rows_to_insert)} filas a sincronizar")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE flujo_caja RESTART IDENTITY")
            if rows_to_insert:
                cur.executemany(
                    """
                    INSERT INTO flujo_caja (id, fila, raw)
                    VALUES (%(id)s, %(fila)s, %(raw)s)
                    ON CONFLICT (id) DO UPDATE
                        SET fila = EXCLUDED.fila,
                            raw  = EXCLUDED.raw,
                            synced_at = now()
                    """,
                    [
                        {"id": r["id"], "fila": r["fila"], "raw": Json(r["raw"])}
                        for r in rows_to_insert
                    ],
                )
        conn.commit()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM flujo_caja")
            n_db = cur.fetchone()[0]
    print(
        f"[flujo_caja] Sincronizadas {len(rows_to_insert)} filas "
        f"(verificación en BD: count(*)={n_db})"
    )
    return len(rows_to_insert)
