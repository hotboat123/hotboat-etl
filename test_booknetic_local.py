"""
Script para probar la exportación de Booknetic localmente
Ejecuta: python test_booknetic_local.py
"""
import os
import sys

# Configurar credenciales directamente (temporal, para testing)
os.environ["BOOKNETIC_URL"] = "https://hotboatchile.com/wp-login.php"
os.environ["BOOKNETIC_USERNAME"] = "hotboatvillarrica@gmail.com"
os.environ["BOOKNETIC_PASSWORD"] = "Hotboat777"

# Deshabilitar carga a base de datos (solo exportar CSV)
os.environ["USE_DATABASE"] = "false"

print("=" * 60)
print("TEST LOCAL - Booknetic Export")
print("=" * 60)
print()

# Opción 1: Ejecutar el script mejorado standalone (SIN base de datos)
print("OPCIÓN 1: Ejecutar script standalone (Selenium)")
print("Este script descargará los datos y los mostrará en consola")
print("NO requiere base de datos PostgreSQL")
print()

try:
    from jobs.booknetic_export_improved import main as export_main
    print("✅ Módulo booknetic_export_improved encontrado")
    print()
    print("Iniciando exportación...")
    print("-" * 60)
    export_main()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("FIN DEL TEST")
print("=" * 60)

