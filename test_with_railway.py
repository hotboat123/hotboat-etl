"""
Script para probar la carga de CSVs a PostgreSQL usando la DB de Railway
"""
import os
import sys
from pathlib import Path

print("=" * 80)
print("🚂 TEST DE CARGA A POSTGRESQL (RAILWAY)")
print("=" * 80)
print()

# Configurar variables de entorno para Railway
print("⚙️  Configurando variables de entorno...")
print()
print("IMPORTANTE: Este script cargará los CSVs locales a la base de datos de Railway")
print("Los datos actuales en Railway serán REEMPLAZADOS (TRUNCATE + INSERT)")
print()

# Variables de Railway (ajusta estas según tu configuración)
RAILWAY_DB_CONFIG = {
    "PGHOST": "autorack.proxy.rlwy.net",
    "PGPORT": "31093",
    "PGUSER": "postgres",
    "PGPASSWORD": "CxNTjRZqVQnUTzHUUeOYUITfqGWBXKVv",
    "PGDATABASE": "railway"
}

# Construir DATABASE_URL
database_url = f"postgresql://{RAILWAY_DB_CONFIG['PGUSER']}:{RAILWAY_DB_CONFIG['PGPASSWORD']}@{RAILWAY_DB_CONFIG['PGHOST']}:{RAILWAY_DB_CONFIG['PGPORT']}/{RAILWAY_DB_CONFIG['PGDATABASE']}"
os.environ["DATABASE_URL"] = database_url

print("✅ DATABASE_URL configurado")
print()

# Verificar que existen los CSVs
downloads_dir = Path("downloads")
if not downloads_dir.exists():
    print("❌ Error: La carpeta 'downloads' no existe")
    sys.exit(1)

customers_files = sorted(downloads_dir.glob("customers_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
appointments_files = sorted(downloads_dir.glob("appointments_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
payments_files = sorted(downloads_dir.glob("payments_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)

if not (customers_files and appointments_files and payments_files):
    print("❌ Error: No se encontraron todos los CSVs necesarios")
    sys.exit(1)

print("📋 Archivos CSV encontrados:")
print(f"   - Customers: {customers_files[0].name}")
print(f"   - Appointments: {appointments_files[0].name}")
print(f"   - Payments: {payments_files[0].name}")
print()

# Preguntar confirmación
print("⚠️  ¿Estás seguro de que quieres continuar? (esto reemplazará los datos en Railway)")
print("   Escribe 'SI' para continuar o cualquier otra cosa para cancelar:")
confirmation = input().strip().upper()

if confirmation != "SI":
    print("❌ Operación cancelada")
    sys.exit(0)

print()
print("=" * 80)
print("🚀 INICIANDO CARGA A POSTGRESQL")
print("=" * 80)
print()

try:
    # 1. Verificar conexión
    print("1️⃣ Verificando conexión a PostgreSQL...")
    from db.connection import get_connection
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), version()")
            db_name, version = cur.fetchone()
            print(f"   ✅ Conectado a: {db_name}")
            print(f"      {version.split(',')[0]}")
    print()
    
    # 2. Mostrar estado actual
    print("2️⃣ Estado actual de las tablas:")
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in ["booknetic_customers", "booknetic_appointments", "booknetic_payments"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"   {table}: {count} registros")
    print()
    
    # 3. Cargar CSVs
    print("3️⃣ Procesando y cargando CSVs...")
    from jobs.booknetic_export_improved import parse_csv_file, map_customers_to_db, map_appointments_to_db, map_payments_to_db
    from db.utils import replace_all
    
    results = {}
    
    # Customers
    print("   📁 Cargando customers...")
    rows = parse_csv_file(customers_files[0])
    mapped = map_customers_to_db(rows)
    affected = replace_all(table="booknetic_customers", rows=mapped)
    results["customers"] = affected
    print(f"      ✅ {affected} customers cargados")
    
    # Appointments
    print("   📁 Cargando appointments...")
    rows = parse_csv_file(appointments_files[0])
    mapped = map_appointments_to_db(rows)
    affected = replace_all(table="booknetic_appointments", rows=mapped)
    results["appointments"] = affected
    print(f"      ✅ {affected} appointments cargados")
    
    # Payments
    print("   📁 Cargando payments...")
    rows = parse_csv_file(payments_files[0])
    mapped = map_payments_to_db(rows)
    affected = replace_all(table="booknetic_payments", rows=mapped)
    results["payments"] = affected
    print(f"      ✅ {affected} payments cargados")
    
    print()
    
    # 4. Verificar estado final
    print("4️⃣ Estado final de las tablas:")
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in ["booknetic_customers", "booknetic_appointments", "booknetic_payments"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"   {table}: {count} registros")
                
                # Mostrar algunos registros de ejemplo
                cur.execute(f"SELECT * FROM {table} LIMIT 2")
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]
                print(f"      Ejemplo de registros:")
                for row in rows:
                    print(f"         {dict(zip(colnames, row))}")
    
    print()
    print("=" * 80)
    print("✅ CARGA COMPLETADA EXITOSAMENTE")
    print("=" * 80)
    print()
    print("📊 Resumen:")
    for key, value in results.items():
        print(f"   - {key}: {value} registros")
    print()
    
except Exception as e:
    print(f"❌ Error durante la carga: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


