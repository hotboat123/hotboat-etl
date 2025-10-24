"""
Script para probar la exportación de Booknetic CON carga a PostgreSQL
Ejecuta: python test_booknetic_with_db.py
"""
import os
import sys

# Configurar credenciales directamente (temporal, para testing)
os.environ["BOOKNETIC_URL"] = "https://hotboatchile.com/wp-login.php"
os.environ["BOOKNETIC_USERNAME"] = "hotboatvillarrica@gmail.com"
os.environ["BOOKNETIC_PASSWORD"] = "Hotboat777"

# Habilitar carga a base de datos
os.environ["USE_DATABASE"] = "true"

# DATABASE_URL - Cambia esto por tu conexión local o Railway
# Para Railway, esto se configura automáticamente
# Para local: postgresql://usuario:password@localhost:5432/hotboat_etl
if "DATABASE_URL" not in os.environ:
    print("⚠️ DATABASE_URL no está configurado")
    print("Para test local, configura:")
    print('os.environ["DATABASE_URL"] = "postgresql://usuario:password@localhost:5432/hotboat_etl"')
    print("\nPara test SIN base de datos, usa: python test_booknetic_local.py")
    sys.exit(1)

print("=" * 60)
print("TEST CON BASE DE DATOS - Booknetic Export")
print("=" * 60)
print(f"DATABASE_URL: {os.environ['DATABASE_URL'][:30]}...")
print()

try:
    from jobs.booknetic_export_improved import main as export_main
    print("✅ Módulo booknetic_export_improved encontrado")
    print()
    print("Iniciando exportación y carga a DB...")
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

