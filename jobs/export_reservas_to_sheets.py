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


def flatten_json_data(raw_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplana el diccionario JSON en columnas individuales.
    Maneja extras_json como un JSON string o lo expande si es necesario.
    """
    flattened = {}
    
    for key, value in raw_dict.items():
        if key == 'extras_json' and isinstance(value, dict):
            # Convertir extras_json a string JSON para Google Sheets
            flattened['extras_json'] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (dict, list)):
            # Otros objetos complejos también se convierten a JSON string
            flattened[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flattened[key] = ""
        else:
            flattened[key] = str(value)
    
    return flattened


def fetch_reservas_data() -> tuple[List[str], List[List[Any]]]:
    """
    Obtiene todos los datos de la tabla Reservas_Con_Extras_Sheets
    y los formatea para Google Sheets.
    
    Returns:
        tuple: (headers, rows) donde headers es lista de nombres de columnas
               y rows es lista de listas con los valores
    """
    print("[export] Conectando a la base de datos...")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Obtener todas las filas
            cur.execute("""
                SELECT id, raw, source, created_at, updated_at
                FROM "Reservas_Con_Extras_Sheets"
                ORDER BY id
            """)
            
            db_rows = cur.fetchall()
            print(f"[export] Filas obtenidas de la BD: {len(db_rows)}")
    
    if not db_rows:
        print("[export] ATENCION: No hay datos en la tabla Reservas_Con_Extras_Sheets")
        return [], []
    
    # Recolectar todas las claves posibles del JSON
    all_keys = set()
    flattened_rows = []
    
    for db_row in db_rows:
        row_id, raw_json, source, created_at, updated_at = db_row
        
        # Aplanar el JSON
        flattened = flatten_json_data(raw_json)
        
        # Agregar metadatos de la tabla
        flattened['_db_id'] = str(row_id)
        flattened['_source'] = source or ""
        flattened['_created_at'] = created_at.isoformat() if created_at else ""
        flattened['_updated_at'] = updated_at.isoformat() if updated_at else ""
        
        all_keys.update(flattened.keys())
        flattened_rows.append(flattened)
    
    # Ordenar las claves para tener un orden consistente
    # Priorizar campos importantes al inicio
    priority_fields = [
        '_db_id', 'id', 'reservation_id', 'appointment_id',
        'fecha', 'hora', 'nombre_cliente', 'email', 'telefono',
        'servicio', 'num_adultos', 'num_ninos', 'num_personas',
        'ingreso_total', 'ingreso_reserva', 'ingreso_extras',
        'costo_operativo_total', 'costo_operativo_fijo', 'costo_operativo_variable',
        'status', 'ciudad_origen', 'como_supieron', 'tipo_clientes', 'categoria_clientes',
        'clima_del_dia', 'tiene_cruce', 'extras_json',
        '_source', '_created_at', '_updated_at'
    ]
    
    # Crear lista ordenada de headers
    headers = []
    for field in priority_fields:
        if field in all_keys:
            headers.append(field)
            all_keys.remove(field)
    
    # Agregar campos restantes alfabéticamente
    headers.extend(sorted(all_keys))
    
    # Convertir filas a listas en el orden de los headers
    rows = []
    for flat_row in flattened_rows:
        row_values = [flat_row.get(header, "") for header in headers]
        rows.append(row_values)
    
    print(f"[export] Headers: {len(headers)} columnas")
    print(f"[export] Filas procesadas: {len(rows)}")
    
    return headers, rows


def update_google_sheet(headers: List[str], rows: List[List[Any]]):
    """
    Actualiza Google Sheets con los datos de la tabla.
    Borra el contenido anterior y escribe el nuevo.
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
        
        # Limpiar todo el contenido anterior
        print(f"[export] Limpiando contenido anterior...")
        worksheet.clear()
        
        # Preparar datos: headers + rows
        all_data = [headers] + rows
        
        print(f"[export] Escribiendo {len(rows)} filas en Google Sheets...")
        
        # Escribir todo de una vez (más eficiente)
        worksheet.update(range_name='A1', values=all_data)
        
        # Formatear la primera fila (headers) como encabezado
        print(f"[export] Formateando headers...")
        worksheet.format('A1:ZZ1', {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8}
        })
        
        # Congelar la primera fila
        worksheet.freeze(rows=1)
        
        print(f"[export] OK Datos exportados exitosamente a '{worksheet_name}'")
        print(f"[export] Total: {len(rows)} filas, {len(headers)} columnas")
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
