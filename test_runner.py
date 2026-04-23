#!/usr/bin/env python3
"""
Script de prueba del runner - ejecuta por 3 minutos para verificar funcionamiento
Con intervalos cortos para prueba rápida
"""

import os
import sys
import time

# Agregar la raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

# Configurar intervalos muy cortos para prueba (en segundos)
os.environ["META_ADS_INTERVAL"] = "120"
os.environ["FLUJO_CAJA_INTERVAL"] = "120"

print("="*60)
print("PRUEBA DEL RUNNER - 3 MINUTOS")
print("="*60)
print("Meta Ads / Flujo Caja: intervalo 120s (si están habilitados por env)")
print("El runner ya no incluye Sheets ni export Reservas_Con_Extras_Sheets")
print("Presiona Ctrl+C para detener antes de tiempo")
print("="*60)
print()

# Importar y ejecutar el runner
from jobs import runner

# Modificar la función main para que se detenga después de 3 minutos
original_main = runner.main

def test_main():
    """Versión modificada del main que se detiene después de 3 minutos"""
    import time
    import threading
    
    # Timer para detener después de 3 minutos
    def stop_after_timeout():
        time.sleep(180)  # 3 minutos
        print("\n" + "="*60)
        print("TIEMPO DE PRUEBA COMPLETADO (3 minutos)")
        print("="*60)
        os._exit(0)
    
    timer_thread = threading.Thread(target=stop_after_timeout, daemon=True)
    timer_thread.start()
    
    # Ejecutar el runner normal
    try:
        original_main()
    except (KeyboardInterrupt, SystemExit):
        print("\n" + "="*60)
        print("Prueba detenida por el usuario")
        print("="*60)

if __name__ == "__main__":
    test_main()
