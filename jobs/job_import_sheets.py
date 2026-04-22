import base64
import hashlib
import json
import os
import uuid
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


def _process_generic_worksheet(ws, worksheet_name: str, rows: List[List[Any]]) -> int:
    """Procesa hojas genéricas (Stock, Precios Extras) leyendo todo tal cual"""
    print(f"[sheets] Procesando hoja genérica: {worksheet_name}")
    
    if not rows:
        return 0
    
    # Asumir que la primera fila son los encabezados
    headers = [str(h).strip() if h else f"col_{i+1}" for i, h in enumerate(rows[0])]
    data_rows = rows[1:] if len(rows) > 1 else []
    
    print(f"[sheets] Headers: {headers}")
    print(f"[sheets] Filas de datos: {len(data_rows)}")
    
    # Crear registros con todos los datos
    records: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(data_rows):
        # Crear diccionario con todos los valores
        record: Dict[str, Any] = {}
        for col_idx, header in enumerate(headers):
            value = row[col_idx] if col_idx < len(row) else None
            if value is not None and str(value).strip():
                record[header] = str(value).strip()
        
        # Solo agregar si el registro tiene al menos un campo con valor
        if record:
            # Generar ID basado en todos los valores del registro
            pieces = [f"{k}={v}" for k, v in sorted(record.items())]
            id_raw = f"{worksheet_name}||{row_idx}||{'|'.join(pieces)}"
            record["id"] = hashlib.sha1(id_raw.encode("utf-8")).hexdigest()
            records.append(record)
    
    print(f"[sheets] Registros procesados: {len(records)}")
    
    # Determinar tabla destino
    target_table = "Stock" if worksheet_name == "Stock" else "Precios Extras"
    
    # Transformar para la base de datos
    transformed = [_transform_generic(r) for r in records]
    
    # Upsert a tabla destino
    affected = upsert_many(
        table=target_table,
        rows=transformed,
        conflict_columns=["id"],
        update_columns=["raw", "source"],
    )
    
    print(f"[sheets] Filas afectadas en '{target_table}': {affected}")
    return affected


def _ensure_id(record: Dict[str, Any], worksheet_name: Optional[str] = None) -> None:
    if record.get("id"):
        return
    
    # Para hojas genéricas (Stock, Precios Extras), generar ID basado en todos los campos
    if worksheet_name in ["Stock", "Precios Extras"]:
        # Generar ID basado en todos los campos del registro
        pieces = [f"{k}={str(v).strip()}" for k, v in sorted(record.items()) if v]
        if pieces:
            fallback_raw = "|".join(pieces)
            record["id"] = hashlib.sha1(fallback_raw.encode("utf-8")).hexdigest()
        else:
            # Si no hay campos, usar un UUID (no ideal pero funcional)
            record["id"] = hashlib.sha1(str(uuid.uuid4()).encode("utf-8")).hexdigest()
        return
    
    # Para otras hojas, usar la lógica original con campos específicos
    fields_csv = os.getenv("SHEETS_ID_FIELDS", "email,marca_temporal").strip()
    fields = [f.strip().lower().replace(" ", "_") for f in fields_csv.split(",") if f.strip()]
    if not fields:
        # Si no hay campos configurados, intentar generar ID con todos los campos disponibles
        pieces = [f"{k}={str(v).strip()}" for k, v in sorted(record.items()) if v and k != "id"]
        if pieces:
            fallback_raw = "|".join(pieces)
            record["id"] = hashlib.sha1(fallback_raw.encode("utf-8")).hexdigest()
        return
    parts: List[str] = []
    for f in fields:
        v = record.get(f)
        parts.append("" if v is None else str(v))
    raw = "||".join(parts)
    if raw.strip():  # Solo generar ID si hay al menos un campo con valor
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()  # stable deterministic id
        record["id"] = digest


def _process_worksheet(ws, worksheet_name: str) -> int:
    """Procesa una hoja individual y retorna el número de filas afectadas"""
    print(f"[sheets] Procesando worksheet: {worksheet_name}")
    rows = ws.get_all_values()
    if not rows:
        print(f"[sheets] Worksheet '{worksheet_name}' está vacía")
        return 0
    
    # Para hojas genéricas (Stock, Precios Extras), leer tal cual sin mapeos complejos
    if worksheet_name in ["Stock", "Precios Extras"]:
        return _process_generic_worksheet(ws, worksheet_name, rows)
    
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
        _ensure_id(rec, worksheet_name)

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
        # Todas las demás hojas van a "Informacion Reservas"
        target_table = "Informacion Reservas"
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
    
    return affected


def run() -> int:
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SHEETS_SPREADSHEET_ID no está definido")

    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)

    print(f"[sheets] spreadsheet_id={spreadsheet_id}")
    
    # Obtener todas las hojas disponibles
    all_worksheets = [ws.title for ws in sh.worksheets()]
    print(f"[sheets] Hojas disponibles en el spreadsheet: {all_worksheets}")
    
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
    
    # SIEMPRE agregar Stock y Precios Extras si existen (además de las configuradas)
    # Esto asegura que estas hojas se procesen siempre
    if "Stock" in all_worksheets and "Stock" not in worksheet_names:
        worksheet_names.append("Stock")
        print(f"[sheets] Agregando hoja 'Stock' a la lista de procesamiento")
    if "Precios Extras" in all_worksheets and "Precios Extras" not in worksheet_names:
        worksheet_names.append("Precios Extras")
        print(f"[sheets] Agregando hoja 'Precios Extras' a la lista de procesamiento")
    
    # Si no hay hojas configuradas o solo hay Sheet1, intentar auto-detectar
    if not worksheet_names or (len(worksheet_names) == 1 and worksheet_names[0] == "Sheet1"):
        worksheet_names = []
        # Buscar "Informacion Reserva"
        if "Informacion Reserva" in all_worksheets:
            worksheet_names.append("Informacion Reserva")
        # Buscar hoja de leads (puede tener varios nombres comunes)
        leads_sheet_names = [name for name in all_worksheets if name.lower() in ["leads", "lead", "formulario", "contactos"]]
        if leads_sheet_names:
            worksheet_names.extend(leads_sheet_names[:1])  # Solo la primera encontrada
        
        if not worksheet_names:
            # Fallback: usar la primera hoja
            worksheet_names = [all_worksheets[0]] if all_worksheets else ["Sheet1"]
        
        print(f"[sheets] Hojas a procesar (auto-detectadas): {worksheet_names}")
    
    print(f"[sheets] Hojas finales a procesar: {worksheet_names}")

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


