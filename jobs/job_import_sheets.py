import base64
import json
import os
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials

from db.utils import upsert_many


def _get_gspread_client():
    b64 = os.getenv("GOOGLE_SA_JSON_BASE64")
    if not b64:
        raise RuntimeError("GOOGLE_SA_JSON_BASE64 no está definido")
    info = json.loads(base64.b64decode(b64).decode("utf-8"))
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def _map_row_by_headers(headers: List[str], row: List[Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for i, h in enumerate(headers):
        key = (h or "").strip().lower().replace(" ", "_")
        values[key] = row[i] if i < len(row) else None
    return values


def _transform(record: Dict[str, Any]) -> Dict[str, Any]:
    # Personaliza este mapeo a tu esquema objetivo
    # Ejemplo de columnas esperadas en Sheets: id, name, email, phone
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "email": record.get("email"),
        "phone": record.get("phone"),
        "source": "sheets",
    }


def run() -> int:
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    worksheet_name = os.getenv("SHEETS_WORKSHEET_NAME", "Sheet1")
    if not spreadsheet_id:
        raise RuntimeError("SHEETS_SPREADSHEET_ID no está definido")

    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)

    rows = ws.get_all_values()
    if not rows:
        return 0
    headers = rows[0]
    data_rows = rows[1:]

    mapped: List[Dict[str, Any]] = [_map_row_by_headers(headers, r) for r in data_rows]
    transformed = [_transform(m) for m in mapped if m.get("id")]

    # Upsert a tabla destino
    affected = upsert_many(
        table="leads",
        rows=transformed,
        conflict_columns=["id"],
        update_columns=["name", "email", "phone", "source"],
    )
    return affected


