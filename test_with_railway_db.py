"""
Test completo: Exporta CSV y carga a PostgreSQL de Railway
Este script se conecta a la base de datos de Railway desde local
"""
import os
import sys

# ========================================
# CONFIGURA AQUÍ TU DATABASE_URL DE RAILWAY
# ========================================
# Ve a Railway → PostgreSQL → Variables → DATABASE_URL
# Copia y pega la URL completa aquí:

DATABASE_URL = "postgresql://postgres:mcxQvhpGaatBzcZNCbVqnGWGBjQpCNYJ@turntable.proxy.rlwy.net:48129/railway"  # <-- PEGA AQUÍ TU URL DE RAILWAY

# Ejemplo:
# DATABASE_URL = "postgresql://postgres:mcxQvhpGaatBzcZNCbVqnGWGBjQpCNYJ@turntable.proxy.rlwy.net:48129/railway"

# ========================================

if not DATABASE_URL:
    print("=" * 60)
    print("⚠️  DATABASE_URL NO CONFIGURADO")
    print("=" * 60)
    print()
    print("Para obtener tu DATABASE_URL de Railway:")
    print("1. Ve a tu proyecto en Railway")
    print("2. Click en el servicio 'PostgreSQL'")
    print("3. Ve a 'Variables' o 'Connect'")
    print("4. Copia el valor de DATABASE_URL")
    print("5. Pégalo en este archivo en la línea 13")
    print()
    print("Debería verse así:")
    print('DATABASE_URL = "postgresql://postgres:XXXX@monorail.proxy.rlwy.net:12345/railway"')
    print("=" * 60)
    sys.exit(1)

# Configurar variables de entorno
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["BOOKNETIC_URL"] = "https://hotboatchile.com/wp-login.php"
os.environ["BOOKNETIC_USERNAME"] = "hotboatvillarrica@gmail.com"
os.environ["BOOKNETIC_PASSWORD"] = "Hotboat777"
os.environ["USE_DATABASE"] = "true"  # HABILITAR carga a DB

print("=" * 60)
print("TEST CON BASE DE DATOS DE RAILWAY")
print("=" * 60)
print(f"📊 Database: {DATABASE_URL[:40]}...")
print("🌐 URL: https://hotboatchile.com")
print("👤 Usuario: hotboatvillarrica@gmail.com")
print("💾 Carga a DB: HABILITADA")
print("=" * 60)
print()

input("Presiona ENTER para continuar (Ctrl+C para cancelar)...")
print()

try:
    from jobs.booknetic_export_improved import main as export_main
    print("✅ Módulo booknetic_export_improved encontrado")
    print()
    print("🚀 Iniciando exportación y carga a PostgreSQL...")
    print("-" * 60)
    print()
    export_main()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("FIN DEL TEST")
print("=" * 60)
print()
print("Para verificar los datos en Railway:")
print("1. Conéctate a tu base de datos con psql o un cliente SQL")
print("2. Ejecuta: SELECT COUNT(*) FROM booknetic_customers;")
print("3. Ejecuta: SELECT COUNT(*) FROM booknetic_appointments;")
print("4. Ejecuta: SELECT COUNT(*) FROM booknetic_payments;")
print("=" * 60)

