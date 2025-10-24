"""
Script interactivo para exportar datos de Booknetic
Pide credenciales al usuario para evitar hardcodearlas
"""
import os
import getpass

print("=" * 60)
print("BOOKNETIC EXPORT - Modo Interactivo")
print("=" * 60)
print()

# Pedir credenciales
print("Por favor ingresa tus credenciales de WordPress:")
username = input("Username (ej: admin): ").strip()
password = getpass.getpass("Password: ").strip()

if not username or not password:
    print("❌ Username y password son requeridos")
    exit(1)

# Configurar variables de entorno
os.environ["BOOKNETIC_URL"] = "https://hotboatchile.com"
os.environ["BOOKNETIC_USERNAME"] = username
os.environ["BOOKNETIC_PASSWORD"] = password

print()
print("✅ Credenciales configuradas")
print(f"🌐 URL: https://hotboatchile.com")
print(f"👤 Username: {username}")
print()
print("🚀 Iniciando exportación...")
print("-" * 60)
print()

try:
    from jobs.booknetic_export_improved import main as export_main
    export_main()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("FIN")
print("=" * 60)

