import base64
import json
import os
from typing import Any, Dict, List, Optional

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


def _apply_col_map(record: Dict[str, Any], col_map: Optional[Dict[str, str]]) -> Dict[str, Any]:
    if not col_map:
        return record
    # Normaliza claves del mapping y aplica: origen -> destino (id/name/email/phone)
    normalized_map: Dict[str, str] = {
        (k or "").strip().lower().replace(" ", "_"): v for k, v in col_map.items()
    }
    result = dict(record)
    for src_key, dest_key in normalized_map.items():
        if dest_key in {"id", "name", "email", "phone"} and dest_key not in result:
            result[dest_key] = record.get(src_key)
    return result


def _transform(record: Dict[str, Any]) -> Dict[str, Any]:
    # Personaliza este mapeo a tu esquema objetivo
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

    print(f"[sheets] spreadsheet_id={spreadsheet_id} worksheet={worksheet_name}")
    rows = ws.get_all_values()
    if not rows:
        return 0
    headers = rows[0]
    data_rows = rows[1:]

    print(f"[sheets] headers(normalized)={[(h or '').strip().lower().replace(' ', '_') for h in headers]}")
    print(f"[sheets] fetched_rows={len(data_rows)}")

    mapped: List[Dict[str, Any]] = [_map_row_by_headers(headers, r) for r in data_rows]

    # Optional column mapping from env JSON: {"id_cliente":"id","correo":"email"}
    col_map_env = os.getenv("SHEETS_COL_MAP_JSON")
    col_map: Optional[Dict[str, str]] = None
    if col_map_env:
        try:
            col_map = json.loads(col_map_env)
        except Exception:  # noqa: BLE001
            col_map = None

    mapped_with_aliases = [_apply_col_map(m, col_map) for m in mapped]

    # Optional: use email as id if id is missing
    use_email_as_id = os.getenv("SHEETS_USE_EMAIL_AS_ID", "").strip().lower() in {"1", "true", "yes", "y"}
    if use_email_as_id:
        for rec in mapped_with_aliases:
            if not rec.get("id") and rec.get("email"):
                rec["id"] = rec.get("email")

    has_id = sum(1 for m in mapped_with_aliases if m.get("id"))
    has_email = sum(1 for m in mapped_with_aliases if m.get("email"))
    sample = mapped_with_aliases[:2]
    print(f"[sheets] records_with_id={has_id} records_with_email={has_email} sample_keys={[list(s.keys()) for s in sample]}")

    transformed = [_transform(m) for m in mapped_with_aliases if m.get("id")]
    print(f"[sheets] to_upsert={len(transformed)}")

    # Upsert a tabla destino
    affected = upsert_many(
        table="leads",
        rows=transformed,
        conflict_columns=["id"],
        update_columns=["name", "email", "phone", "source"],
    )
    return affected


