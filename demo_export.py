#!/usr/bin/env python3
"""
Demo simple: ejecuta el export de reservas a sheets UNA vez
"""

import os
import sys

# Agregar la raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

print("\n" + "="*70)
print("DEMO: EXPORTACION DE Reservas_Con_Extras_Sheets A GOOGLE SHEETS")
print("="*70)
print("\nEste script:")
print("1. Lee la tabla Reservas_Con_Extras_Sheets desde PostgreSQL")
print("2. Exporta los datos a Google Sheets")
print("3. Formatea la hoja para mejor visualización")
print("\n" + "="*70 + "\n")

from jobs.export_reservas_to_sheets import run

try:
    run()
    print("\n" + "="*70)
    print("DEMO COMPLETADA EXITOSAMENTE")
    print("="*70)
    print("\nPuedes ver los datos en Google Sheets:")
    print("https://docs.google.com/spreadsheets/d/1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA")
    print("\nLa hoja 'Reservas_Con_Extras_Sheets' ahora está lista para usar con Looker")
    print("="*70)
except Exception as e:
    print("\n" + "="*70)
    print("ERROR EN LA DEMO")
    print("="*70)
    print(f"\n{e}")
    import traceback
    traceback.print_exc()
