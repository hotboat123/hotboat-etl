import base64
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

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
        "raw": record,
        "source": "sheets",
    }


def _transform_generic(record: Dict[str, Any]) -> Dict[str, Any]:
    # Transformación genérica para hojas que solo almacenan datos en raw (Stock, Precios Extras, etc.)
    return {
        "id": record.get("id"),
        "raw": record,
        "source": "sheets",
    }


def _ensure_id(record: Dict[str, Any]) -> None:
    if record.get("id"):
        return
    fields_csv = os.getenv("SHEETS_ID_FIELDS", "email,marca_temporal").strip()
    fields = [f.strip().lower().replace(" ", "_") for f in fields_csv.split(",") if f.strip()]
    if not fields:
        return
    parts: List[str] = []
    for f in fields:
        v = record.get(f)
        parts.append("" if v is None else str(v))
    raw = "||".join(parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()  # stable deterministic id
    record["id"] = digest


def _process_worksheet(ws, worksheet_name: str) -> int:
    """Procesa una hoja individual y retorna el número de filas afectadas"""
    print(f"[sheets] Procesando worksheet: {worksheet_name}")
    rows = ws.get_all_values()
    if not rows:
        print(f"[sheets] Worksheet '{worksheet_name}' está vacía")
        return 0
    
    has_header = os.getenv("SHEETS_HAS_HEADER", "1").strip().lower() in {"1", "true", "yes", "y"}

    if has_header:
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
    else:
        data_rows = rows
        print(f"[sheets] no header mode. fetched_rows={len(data_rows)}")
        # Column index mapping (1-based). Accepts either {"email":2, "id":5} or {"2":"email"}
        index_map_env = os.getenv("SHEETS_COL_INDEX_JSON", "")
        index_to_dest: Dict[int, str] = {}
        if index_map_env:
            try:
                raw = json.loads(index_map_env)
                # dest->index form
                for k, v in raw.items():
                    if isinstance(v, int):
                        index_to_dest[int(v)] = k
                # index->dest form
                for k, v in raw.items():
                    if isinstance(k, str) and k.isdigit():
                        index_to_dest[int(k)] = str(v)
            except Exception:  # noqa: BLE001
                index_to_dest = {}

        def map_by_index(row: List[Any]) -> Dict[str, Any]:
            rec: Dict[str, Any] = {}
            for idx, dest in index_to_dest.items():
                if dest in {"id", "name", "email", "phone"}:
                    value = row[idx - 1] if 1 <= idx <= len(row) else None
                    rec[dest] = value
            return rec

        mapped_with_aliases = [map_by_index(r) for r in data_rows]

    # First: generate deterministic id from selected fields if missing
    for rec in mapped_with_aliases:
        _ensure_id(rec)

    # Optional: use email as id if id is still missing
    use_email_as_id = os.getenv("SHEETS_USE_EMAIL_AS_ID", "").strip().lower() in {"1", "true", "yes", "y"}
    if use_email_as_id:
        for rec in mapped_with_aliases:
            if not rec.get("id") and rec.get("email"):
                rec["id"] = rec.get("email")

    has_id = sum(1 for m in mapped_with_aliases if m.get("id"))
    has_email = sum(1 for m in mapped_with_aliases if m.get("email"))
    sample = mapped_with_aliases[:2]
    print(f"[sheets] records_with_id={has_id} records_with_email={has_email} sample_keys={[list(s.keys()) for s in sample]}")

    # Determinar tabla destino y función de transformación según el nombre de la hoja
    if worksheet_name == "Informacion Reserva":
        target_table = "Informacion Reservas"
        transform_func = _transform
        update_columns = ["name", "email", "phone", "raw", "source"]
    elif worksheet_name == "Stock":
        target_table = "Stock"
        transform_func = _transform_generic
        update_columns = ["raw", "source"]
    elif worksheet_name == "Precios Extras":
        target_table = "Precios Extras"
        transform_func = _transform_generic
        update_columns = ["raw", "source"]
    else:
        # Hojas de leads (por defecto)
        target_table = "leads"
        transform_func = _transform
        update_columns = ["name", "email", "phone", "raw", "source"]
    
    print(f"[sheets] target_table={target_table}")

    transformed = [transform_func(m) for m in mapped_with_aliases if m.get("id")]
    print(f"[sheets] to_upsert={len(transformed)}")

    # Upsert a tabla destino
    affected = upsert_many(
        table=target_table,
        rows=transformed,
        conflict_columns=["id"],
        update_columns=update_columns,
    )
    
    # Si estamos procesando la hoja de leads (no "Informacion Reserva", "Stock" ni "Precios Extras"), 
    # también copiar los datos a "Informacion Reservas"
    if worksheet_name not in ["Informacion Reserva", "Stock", "Precios Extras"] and target_table == "leads" and transformed:
        print(f"[sheets] Copiando datos de '{worksheet_name}' también a 'Informacion Reservas'")
        # Para copiar a Informacion Reservas, necesitamos usar _transform
        transformed_reservas = [_transform(m) for m in mapped_with_aliases if m.get("id")]
        affected_reservas = upsert_many(
            table="Informacion Reservas",
            rows=transformed_reservas,
            conflict_columns=["id"],
            update_columns=["name", "email", "phone", "raw", "source"],
        )
        print(f"[sheets] Filas afectadas en 'Informacion Reservas': {affected_reservas}")
    
    return affected


def run() -> int:
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SHEETS_SPREADSHEET_ID no está definido")

    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)

    print(f"[sheets] spreadsheet_id={spreadsheet_id}")
    
    # Determinar qué hojas procesar
    # Opción 1: Variable SHEETS_WORKSHEETS (lista separada por comas)
    worksheets_env = os.getenv("SHEETS_WORKSHEETS", "").strip()
    if worksheets_env:
        worksheet_names = [w.strip() for w in worksheets_env.split(",") if w.strip()]
        print(f"[sheets] Procesando hojas desde SHEETS_WORKSHEETS: {worksheet_names}")
    else:
        # Opción 2: Variable SHEETS_WORKSHEET_NAME (una sola hoja, modo legacy)
        worksheet_name = os.getenv("SHEETS_WORKSHEET_NAME", "Sheet1")
        worksheet_names = [worksheet_name]
        print(f"[sheets] Procesando hoja desde SHEETS_WORKSHEET_NAME: {worksheet_name}")
    
    # Si no hay hojas configuradas, intentar procesar hojas comunes
    if not worksheet_names or (len(worksheet_names) == 1 and worksheet_names[0] == "Sheet1"):
        # Intentar encontrar hojas comunes
        all_worksheets = [ws.title for ws in sh.worksheets()]
        print(f"[sheets] Hojas disponibles en el spreadsheet: {all_worksheets}")
        
        worksheet_names = []
        # Buscar "Informacion Reserva"
        if "Informacion Reserva" in all_worksheets:
            worksheet_names.append("Informacion Reserva")
        # Buscar "Stock"
        if "Stock" in all_worksheets:
            worksheet_names.append("Stock")
        # Buscar "Precios Extras"
        if "Precios Extras" in all_worksheets:
            worksheet_names.append("Precios Extras")
        # Buscar hoja de leads (puede tener varios nombres comunes)
        leads_sheet_names = [name for name in all_worksheets if name.lower() in ["leads", "lead", "formulario", "contactos"]]
        if leads_sheet_names:
            worksheet_names.extend(leads_sheet_names[:1])  # Solo la primera encontrada
        
        if not worksheet_names:
            # Fallback: usar la primera hoja
            worksheet_names = [all_worksheets[0]] if all_worksheets else ["Sheet1"]
        
        print(f"[sheets] Hojas a procesar (auto-detectadas): {worksheet_names}")

    total_affected = 0
    
    # Procesar cada hoja
    for worksheet_name in worksheet_names:
        try:
            print(f"\n{'='*60}")
            print(f"[sheets] Procesando hoja: {worksheet_name}")
            print(f"{'='*60}")
            
            ws = sh.worksheet(worksheet_name)
            affected = _process_worksheet(ws, worksheet_name)
            total_affected += affected
            print(f"[sheets] ✅ Hoja '{worksheet_name}' procesada: {affected} filas afectadas")
        except gspread.exceptions.WorksheetNotFound:
            print(f"[sheets] ⚠️ Hoja '{worksheet_name}' no encontrada, saltando...")
        except Exception as e:
            print(f"[sheets] ❌ Error procesando hoja '{worksheet_name}': {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n[sheets] ✅ Total de filas procesadas: {total_affected}")
    return total_affected


