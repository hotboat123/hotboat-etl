"""
Script para verificar la conexión y estructura de la base de datos
"""
import os
import sys

# ========================================
# CONFIGURA AQUÍ TU DATABASE_URL DE RAILWAY
# ========================================
DATABASE_URL = "postgresql://postgres:mcxQvhpGaatBzcZNCbVqnGWGBjQpCNYJ@turntable.proxy.rlwy.net:48129/railway"  # <-- PEGA AQUÍ TU URL DE RAILWAY

# ========================================

if not DATABASE_URL:
    print("⚠️  DATABASE_URL NO CONFIGURADO")
    print("Edita este archivo y pega tu DATABASE_URL de Railway")
    sys.exit(1)

os.environ["DATABASE_URL"] = DATABASE_URL

print("=" * 60)
print("🔍 VERIFICACIÓN DE BASE DE DATOS")
print("=" * 60)
print()

try:
    from db.connection import get_connection
    
    print("1️⃣ Probando conexión a PostgreSQL...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✅ Conectado a PostgreSQL")
            print(f"   Versión: {version[:50]}...")
            print()
            
            # Verificar tablas
            print("2️⃣ Verificando tablas...")
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            expected_tables = [
                'booknetic_customers',
                'booknetic_appointments',
                'booknetic_payments',
                'job_runs'
            ]
            
            for table in expected_tables:
                if table in tables:
                    print(f"   ✅ {table}")
                    
                    # Contar registros
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cur.fetchone()[0]
                    print(f"      └─ {count} registros")
                else:
                    print(f"   ❌ {table} - NO EXISTE")
            
            print()
            
            # Verificar si faltan tablas
            missing_tables = [t for t in expected_tables if t not in tables]
            
            if missing_tables:
                print("⚠️  FALTAN TABLAS!")
                print()
                print("Para crear las tablas, necesitas ejecutar el schema SQL:")
                print()
                print("Opción A: Desde Railway Web Console")
                print("  1. Ve a PostgreSQL → Data")
                print("  2. Copia el contenido de sql/schema.sql")
                print("  3. Pégalo y ejecuta")
                print()
                print("Opción B: Desde psql local")
                print(f'  psql "{DATABASE_URL}" -f sql/schema.sql')
                print(f'  psql "{DATABASE_URL}" -f sql/job_meta.sql')
                print()
            else:
                print("✅ TODAS LAS TABLAS ESTÁN CONFIGURADAS CORRECTAMENTE")
                print()
                print("🎉 Tu base de datos está lista para usar!")
                print()
                print("Ahora puedes ejecutar:")
                print("  python test_with_railway_db.py")
            
            print()
            print("=" * 60)
            
except Exception as e:
    print(f"❌ Error de conexión: {e}")
    print()
    print("Verifica que:")
    print("1. El DATABASE_URL sea correcto")
    print("2. Tengas acceso a internet")
    print("3. Railway permita conexiones desde tu IP")
    import traceback
    traceback.print_exc()

