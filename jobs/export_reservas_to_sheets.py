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
    Actualiza Google Sheets en modo append-only:
    - Nunca borra histórico.
    - Solo agrega filas nuevas por fecha/id.
    """
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SHEETS_SPREADSHEET_ID no está definido")
    
    # Nombre de la hoja donde se exportarán los datos
    worksheet_name = os.getenv("SHEETS_EXPORT_WORKSHEET_NAME", "Reservas_Con_Extras_Sheets")
    
    print(f"[export] Conectando a Google Sheets (ID: {spreadsheet_id})...")
    
    try:
        gc = get_gspread_client()
        spreadsheet = gc.open_by_key(spreadsheet_id)
        
        # Intentar obtener la hoja, si no existe, crearla
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            print(f"[export] Hoja '{worksheet_name}' encontrada")
        except gspread.exceptions.WorksheetNotFound:
            print(f"[export] Hoja '{worksheet_name}' no encontrada, creando...")
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=50)
        
        existing_data = worksheet.get_all_values()

        # Primer poblamiento: escribir todo
        if not existing_data:
            all_data = [headers] + rows
            print(f"[export] Hoja vacía, escribiendo carga inicial ({len(rows)} filas)...")
            worksheet.update(range_name="A1", values=all_data)

            print("[export] Formateando headers...")
            worksheet.format("A1:ZZ1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8}
            })
            worksheet.freeze(rows=1)

            print(f"[export] OK Carga inicial completada en '{worksheet_name}'")
            print(f"[export] Total: {len(rows)} filas, {len(headers)} columnas")
            print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            return

        existing_headers = existing_data[0]
        if existing_headers != headers:
            print("[export] ATENCION: Headers en Sheets difieren de la BD.")
            print("[export] Se usará el orden de columnas de Sheets para append.")

        # Índices en BD
        db_idx = {name: idx for idx, name in enumerate(headers)}
        db_fecha_idx = db_idx.get("fecha")
        db_id_idx = db_idx.get("id")

        # Índices en Sheets
        sh_idx = {name: idx for idx, name in enumerate(existing_headers)}
        sh_fecha_idx = sh_idx.get("fecha")
        sh_id_idx = sh_idx.get("id")

        if sh_fecha_idx is None or db_fecha_idx is None:
            print("[export] ATENCION: No existe columna 'fecha' en Sheets o BD; no se puede aplicar filtro por fecha.")
            return
        if sh_id_idx is None or db_id_idx is None:
            print("[export] ATENCION: No existe columna 'id' en Sheets o BD; no se puede deduplicar de forma segura.")
            return

        # Fecha de corte = fecha de la ultima fila con fecha válida en Google Sheets
        cutoff_date = None
        existing_ids = set()
        for r in existing_data[1:]:
            if sh_id_idx < len(r):
                rid = r[sh_id_idx].strip()
                if rid:
                    existing_ids.add(rid)

        for r in reversed(existing_data[1:]):
            if sh_fecha_idx < len(r):
                d = parse_date_safe(r[sh_fecha_idx])
                if d:
                    cutoff_date = d
                    break

        if cutoff_date is None:
            print("[export] ATENCION: No se encontró fecha válida en la hoja. Para evitar duplicados no se agregará nada.")
            print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            return

        # Ordenar filas de BD por fecha ascendente para append consistente
        def sort_key(db_row):
            d = parse_date_safe(db_row[db_fecha_idx]) if db_fecha_idx < len(db_row) else None
            return (d is None, d)

        rows_sorted = sorted(rows, key=sort_key)
        rows_to_append = []

        for db_row in rows_sorted:
            db_date = parse_date_safe(db_row[db_fecha_idx]) if db_fecha_idx < len(db_row) else None
            db_row_id = str(db_row[db_id_idx]).strip() if db_id_idx < len(db_row) else ""

            # No duplicar IDs que ya existen en Google Sheets
            if db_row_id and db_row_id in existing_ids:
                continue

            # Regla pedida: solo agregar desde el día siguiente al último cargado
            # (fecha estrictamente mayor al cutoff)
            if cutoff_date is not None and db_date is not None and db_date <= cutoff_date:
                continue

            db_map = {headers[i]: db_row[i] for i in range(len(headers))}
            new_row = [db_map.get(col, "") for col in existing_headers]
            rows_to_append.append(new_row)

        if not rows_to_append:
            print("[export] OK No hay filas nuevas para agregar (append-only).")
            print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            return

        print(f"[export] Fecha de corte detectada en hoja: {cutoff_date.isoformat()}")
        print(f"[export] Agregando {len(rows_to_append)} filas nuevas (append-only)...")
        worksheet.append_rows(rows_to_append, value_input_option="RAW")

        print(f"[export] OK Datos actualizados exitosamente en '{worksheet_name}'")
        print(f"[export] Filas nuevas agregadas: {len(rows_to_append)}")
        print(f"[export] Filas totales BD consultadas: {len(rows)}")
        print(f"[export] URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
        
    except Exception as e:
        print(f"[export] ERROR actualizando Google Sheets: {e}")
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
