#!/usr/bin/env python3
"""Script para verificar que todos los jobs se pueden importar correctamente"""

import os
import sys

# Agregar la raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("VERIFICANDO IMPORTACIONES DE JOBS")
print("="*60)

# Job 1: Booknetic Scrape
try:
    from jobs.job_scrape_booknetic import run as run_booknetic
    print("[OK] job_scrape_booknetic importado correctamente")
except Exception as e:
    print(f"[ERROR] job_scrape_booknetic: {e}")

# Job 2: Sheets Import
try:
    from jobs.job_import_sheets import run as run_sheets
    print("[OK] job_import_sheets importado correctamente")
except Exception as e:
    print(f"[ERROR] job_import_sheets: {e}")

# Job 3: Export Reservas to Sheets (NUEVO)
try:
    from jobs.export_reservas_to_sheets import run as run_export_reservas
    print("[OK] export_reservas_to_sheets importado correctamente")
except Exception as e:
    print(f"[ERROR] export_reservas_to_sheets: {e}")

print("\n" + "="*60)
print("VERIFICACION COMPLETADA")
print("="*60)
