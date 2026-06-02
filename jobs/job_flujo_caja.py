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
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from db.connection import get_connection

SHEET_NAME_DEFAULT = "consolidad flujo caja"

ACTUAL_COLUMNS = ["fecha", "descripci_n", "cargos", "abonos", "saldo",
                  "categor_a_1", "categor_a_2", "observaciones", "origen"]


def _normalize_col(header: str) -> str:
    """Convierte un encabezado del sheet al nombre de columna SQL (ej: 'Categoría 1' → 'categor_a_1')."""
    chars = []
    for ch in header.lower():
        if ch.isascii() and ch.isalnum():
            chars.append(ch)
        else:
            chars.append("_")
    return "".join(chars).strip("_")


def _parse_date(value: Any) -> Optional[object]:
    """Parsea fecha desde texto (dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd). Retorna datetime.date o None."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_numeric(value: Any) -> Optional[Decimal]:
    """Parsea número desde texto con formato CLP ($25,510 → 25510). Retorna Decimal o None."""
    if not value:
        return None
    text = str(value).strip().replace("$", "").replace("\xa0", "").replace(" ", "")
    if not text or text in ("-", "–", "—"):
        return None
    if "," in text and "." not in text:
        # Coma como separador de miles: $25,510 → 25510
        text = text.replace(",", "")
    elif "," in text and "." in text:
        # Determinar cuál es decimal por posición (el último separador es el decimal)
        if text.rfind(",") > text.rfind("."):
            # Formato chileno: 1.234,56 → 1234.56
            text = text.replace(".", "").replace(",", ".")
        else:
            # Formato anglosajón: 1,234.56 → 1234.56
            text = text.replace(",", "")
    elif text.count(".") > 1:
        # Múltiples puntos = miles sin decimal: 1.234.567 → 1234567
        text = text.replace(".", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


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

    # Pre-calcular columnas tipadas para flujo_caja_actual
    actual_rows = []
    for r in rows_to_insert:
        col_map = {_normalize_col(k): v for k, v in r["raw"].items()}
        actual_rows.append({
            "id":            r["id"],
            "fila":          r["fila"],
            "fecha":         _parse_date(col_map.get("fecha")),
            "descripci_n":   col_map.get("descripci_n") or None,
            "cargos":        _parse_numeric(col_map.get("cargos")),
            "abonos":        _parse_numeric(col_map.get("abonos")),
            "saldo":         _parse_numeric(col_map.get("saldo")),
            "categor_a_1":   col_map.get("categor_a_1") or None,
            "categor_a_2":   col_map.get("categor_a_2") or None,
            "observaciones": col_map.get("observaciones") or None,
            "origen":        col_map.get("origen") or None,
        })

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE flujo_caja RESTART IDENTITY")
            cur.execute("TRUNCATE TABLE flujo_caja_actual RESTART IDENTITY")
            if rows_to_insert:
                cur.executemany(
                    """
                    INSERT INTO flujo_caja (id, fila, raw)
                    VALUES (%(id)s, %(fila)s, %(raw)s::jsonb)
                    ON CONFLICT (id) DO UPDATE
                        SET fila = EXCLUDED.fila,
                            raw  = EXCLUDED.raw,
                            synced_at = now()
                    """,
                    [
                        {**r, "raw": json.dumps(r["raw"], ensure_ascii=False)}
                        for r in rows_to_insert
                    ],
                )
                cur.executemany(
                    """
                    INSERT INTO flujo_caja_actual
                        (id, fila, fecha, descripci_n, cargos, abonos, saldo,
                         categor_a_1, categor_a_2, observaciones, origen)
                    VALUES
                        (%(id)s, %(fila)s, %(fecha)s, %(descripci_n)s, %(cargos)s,
                         %(abonos)s, %(saldo)s, %(categor_a_1)s, %(categor_a_2)s,
                         %(observaciones)s, %(origen)s)
                    ON CONFLICT (id) DO UPDATE
                        SET fila          = EXCLUDED.fila,
                            fecha         = EXCLUDED.fecha,
                            descripci_n   = EXCLUDED.descripci_n,
                            cargos        = EXCLUDED.cargos,
                            abonos        = EXCLUDED.abonos,
                            saldo         = EXCLUDED.saldo,
                            categor_a_1   = EXCLUDED.categor_a_1,
                            categor_a_2   = EXCLUDED.categor_a_2,
                            observaciones = EXCLUDED.observaciones,
                            origen        = EXCLUDED.origen,
                            synced_at     = now()
                    """,
                    actual_rows,
                )
        conn.commit()

    print(f"[flujo_caja] Sincronizadas {len(rows_to_insert)} filas")
    return len(rows_to_insert)
