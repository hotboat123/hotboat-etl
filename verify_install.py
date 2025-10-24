"""
Script para verificar que todos los módulos necesarios están instalados
"""
import sys

print("=" * 60)
print("🔍 VERIFICACIÓN DE MÓDULOS INSTALADOS")
print("=" * 60)
print()
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print()

required_modules = [
    "apscheduler",
    "psycopg",
    "psycopg_pool",
    "gspread",
    "google.auth",
    "dotenv",
    "requests",
    "pytz",
    "tzlocal",
    "selenium",
]

missing = []
installed = []

for module in required_modules:
    try:
        __import__(module)
        installed.append(module)
        print(f"✅ {module}")
    except ImportError as e:
        missing.append(module)
        print(f"❌ {module} - {e}")

print()
print("=" * 60)
print(f"✅ Instalados: {len(installed)}/{len(required_modules)}")
print(f"❌ Faltantes: {len(missing)}/{len(required_modules)}")
print("=" * 60)

if missing:
    print()
    print("⚠️  FALTAN MÓDULOS!")
    print("Ejecuta: pip install -r requirements.txt")
    sys.exit(1)
else:
    print()
    print("🎉 ¡Todos los módulos están instalados correctamente!")
    sys.exit(0)

