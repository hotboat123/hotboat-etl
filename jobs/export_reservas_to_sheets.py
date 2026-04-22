#!/usr/bin/env python3
"""
Script para exportar la tabla Reservas_Con_Extras_Sheets a Google Sheets
y mantenerla actualizada cada 15 minutos para análisis en Looker.
"""

import os
import sys
import json
import base64
from datetime import datetime
from typing import List, Dict, Any

# Agregar la raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from db.connection import get_connection

# Cargar variables de entorno
load_dotenv()


def get_gspread_client():
    """Obtener cliente autenticado de gspread"""
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


def format_value(value: Any) -> str:
    """
    Formatea un valor para Google Sheets.
    """
    if value is None:
        return ""
    elif isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    else:
        return str(value)


def parse_date_safe(value: str):
    """Parsea fecha en formato YYYY-MM-DD; retorna None si no es válida."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Acepta YYYY-MM-DD o timestamp iniciando con fecha
    candidate = text[:10]
    try:
        return datetime.strptime(candidate, "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_reservas_data() -> tuple[List[str], List[List[Any]]]:
    """
    Obtiene todos los datos de la tabla Reservas_Con_Extras_Sheets
    exactamente como están en la base de datos (sin procesar).
    
    Returns:
        tuple: (headers, rows) donde headers es lista de nombres de columnas
               y rows es lista de listas con los valores
    """
    print("[export] Conectando a la base de datos...")
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Verificar si la tabla existe primero
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'Reservas_Con_Extras_Sheets'
                    );
                """)
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    print("[export] ATENCION: La tabla 'Reservas_Con_Extras_Sheets' no existe en la base de datos")
                    print("[export] Esta tabla solo existe en entorno local actualmente")
                    return [], []
                
                # Obtener TODAS las columnas tal cual están en la BD
                cur.execute("""
                    SELECT *
                    FROM "Reservas_Con_Extras_Sheets"
                    ORDER BY id
                """)
                
                db_rows = cur.fetchall()
                
                # Obtener nombres de columnas desde el cursor
                headers = [desc[0] for desc in cur.description]
                
                print(f"[export] Filas obtenidas de la BD: {len(db_rows)}")
                print(f"[export] Columnas: {len(headers)}")
        
        if not db_rows:
            print("[export] ATENCION: No hay datos en la tabla Reservas_Con_Extras_Sheets")
            return [], []
        
        # Convertir filas a formato para Google Sheets
        rows = []
        for db_row in db_rows:
            row_values = [format_value(value) for value in db_row]
            rows.append(row_values)
        
        print(f"[export] Filas procesadas: {len(rows)}")
        
        return headers, rows
        
    except Exception as e:
        print(f"[export] Error al obtener datos: {e}")
        return [], []


def update_google_sheet(headers: List[str], rows: List[List[Any]]):
    """
    Append-only por fecha maxima:
    - Calcula la fecha maxima de toda la hoja actual.
    - Solo agrega filas de la BD cuya fecha es ESTRICTAMENTE mayor a esa fecha maxima.
    - Nunca modifica ni borra lo que ya existe en la hoja.
    """
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SHEETS_SPREADSHEET_ID no está definido")

    worksheet_name = os.getenv("SHEETS_EXPORT_WORKSHEET_NAME", "Reservas_Con_Extras_Sheets")

    print(f"[export] Conectando a Google Sheets (ID: {spreadsheet_id})...")

    try:
        gc = get_gspread_client()
        spreadsheet = gc.open_by_key(spreadsheet_id)

        try:
            ws = spreadsheet.worksheet(worksheet_name)
            print(f"[export] Hoja '{worksheet_name}' encontrada")
        except gspread.exceptions.WorksheetNotFound:
            print(f"[export] Hoja '{worksheet_name}' no encontrada, creando...")
            ws = spreadsheet.add_worksheet(title=worksheet_name, rows=5000, cols=50)

        existing_data = ws.get_all_values()

        # ── CARGA INICIAL (hoja vacia) ──────────────────────────────────────
        if not existing_data:
            print(f"[export] Hoja vacia, escribiendo carga inicial ({len(rows)} filas)...")
            ws.update(range_name="A1", values=[headers] + rows)
            ws.format("A1:ZZ1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8}
            })
            ws.freeze(rows=1)
            print(f"[export] OK Carga inicial. {len(rows)} filas, {len(headers)} columnas")
            print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            return

        # ── MODO APPEND ─────────────────────────────────────────────────────
        existing_headers = existing_data[0]

        db_idx       = {n: i for i, n in enumerate(headers)}
        db_fecha_idx = db_idx.get("fecha")

        sh_idx       = {n: i for i, n in enumerate(existing_headers)}
        sh_fecha_idx = sh_idx.get("fecha")

        if db_fecha_idx is None or sh_fecha_idx is None:
            print("[export] ATENCION: falta columna 'fecha'. No se puede filtrar.")
            return

        # Fecha maxima en toda la hoja actual (recorre todas las filas)
        max_date = None
        for r in existing_data[1:]:
            if sh_fecha_idx < len(r):
                d = parse_date_safe(r[sh_fecha_idx])
                if d and (max_date is None or d > max_date):
                    max_date = d

        if max_date is None:
            print("[export] ATENCION: No hay fechas validas en la hoja. Abortando para evitar duplicados.")
            return

        print(f"[export] Fecha max en hoja: {max_date.isoformat()} | solo se agregan fechas posteriores")

        # Filtrar filas de BD: solo las con fecha ESTRICTAMENTE mayor a max_date
        rows_to_append = []
        for db_row in sorted(rows, key=lambda r: (
            parse_date_safe(r[db_fecha_idx]) is None,
            parse_date_safe(r[db_fecha_idx])
        )):
            db_date = parse_date_safe(db_row[db_fecha_idx]) if db_fecha_idx < len(db_row) else None
            if db_date is None or db_date <= max_date:
                continue
            db_map  = {headers[i]: db_row[i] for i in range(len(headers))}
            new_row = [db_map.get(col, "") for col in existing_headers]
            rows_to_append.append(new_row)

        if not rows_to_append:
            print("[export] OK No hay filas nuevas para agregar.")
            print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            return

        ws.append_rows(rows_to_append, value_input_option="RAW")
        print(f"[export] OK {len(rows_to_append)} filas nuevas agregadas.")
        print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")

    except Exception as e:
        print(f"[export] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


def run():
    """Función principal que ejecuta el export"""
    print(f"\n{'='*70}")
    print(f"[export] EXPORTANDO Reservas_Con_Extras_Sheets A GOOGLE SHEETS")
    print(f"[export] Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*70}\n")
    
    try:
        # 1. Obtener datos de PostgreSQL
        headers, rows = fetch_reservas_data()
        
        if not rows:
            print("[export] ATENCION: No hay datos para exportar")
            return
        
        # 2. Actualizar Google Sheets
        update_google_sheet(headers, rows)
        
        print(f"\n[export] OK Exportacion completada exitosamente")
        
    except Exception as e:
        print(f"\n[export] ERROR durante la exportacion: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run()
