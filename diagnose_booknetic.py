"""
Script de diagnóstico para entender por qué Booknetic no actualiza PostgreSQL
"""
import os
import sys
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("🔍 DIAGNÓSTICO DE BOOKNETIC ETL")
print("=" * 80)
print()

# 1. Verificar variables de entorno
print("1️⃣ VARIABLES DE ENTORNO")
print("-" * 80)
booknetic_url = os.getenv("BOOKNETIC_URL") or os.getenv("BOOKNETIC_BASE_URL")
booknetic_user = os.getenv("BOOKNETIC_USERNAME")
booknetic_pass = os.getenv("BOOKNETIC_PASSWORD")
booknetic_plugin = os.getenv("BOOKNETIC_PLUGIN_MODULE")
database_url = os.getenv("DATABASE_URL")

print(f"   BOOKNETIC_URL: {'✅ ' + booknetic_url if booknetic_url else '❌ NO CONFIGURADO'}")
print(f"   BOOKNETIC_USERNAME: {'✅ Configurado' if booknetic_user else '❌ NO CONFIGURADO'}")
print(f"   BOOKNETIC_PASSWORD: {'✅ Configurado' if booknetic_pass else '❌ NO CONFIGURADO'}")
print(f"   BOOKNETIC_PLUGIN_MODULE: {booknetic_plugin or '❌ NO CONFIGURADO (usa plugins por defecto)'}")
print(f"   DATABASE_URL: {'✅ Configurado' if database_url else '❌ NO CONFIGURADO'}")
print()

# 2. Verificar archivos CSV descargados
print("2️⃣ ARCHIVOS CSV DESCARGADOS")
print("-" * 80)
downloads_dir = Path("downloads")
if not downloads_dir.exists():
    print("   ❌ La carpeta 'downloads' NO EXISTE")
else:
    csv_files = sorted(downloads_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csv_files:
        print("   ⚠️  NO hay archivos CSV en la carpeta downloads")
    else:
        print(f"   ✅ Encontrados {len(csv_files)} archivos CSV:")
        for csv_file in csv_files[:10]:  # Mostrar solo los 10 más recientes
            stat = csv_file.stat()
            size = stat.st_size / 1024  # KB
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"      📄 {csv_file.name}")
            print(f"         Tamaño: {size:.1f} KB | Modificado: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 3. Verificar contenido de los CSVs más recientes
print("3️⃣ CONTENIDO DE CSVs (primeras 3 líneas)")
print("-" * 80)
if downloads_dir.exists():
    for pattern in ["customers_*.csv", "appointments_*.csv", "payments_*.csv"]:
        files = sorted(downloads_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            latest = files[0]
            print(f"   📋 {latest.name}:")
            try:
                with open(latest, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= 3:  # Solo primeras 3 líneas
                            break
                        preview = line.strip()[:100]
                        print(f"      Línea {i+1}: {preview}...")
                # Contar líneas
                with open(latest, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                print(f"      📊 Total de líneas: {line_count}")
            except Exception as e:
                print(f"      ❌ Error leyendo archivo: {e}")
            print()
print()

# 4. Verificar conexión a PostgreSQL
print("4️⃣ CONEXIÓN A POSTGRESQL")
print("-" * 80)
if not database_url:
    print("   ❌ DATABASE_URL no está configurado, no se puede conectar")
else:
    try:
        from db.connection import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Info de la base de datos
                cur.execute("SELECT current_database(), version()")
                db_name, version = cur.fetchone()
                print(f"   ✅ Conexión exitosa a: {db_name}")
                print(f"      PostgreSQL: {version.split(',')[0]}")
                
                # Verificar tablas
                print()
                print("   📊 TABLAS Y REGISTROS:")
                for table in ["booknetic_customers", "booknetic_appointments", "booknetic_payments"]:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        print(f"      {table}: {count} registros")
                        
                        # Mostrar última actualización (si hay datos)
                        if count > 0:
                            cur.execute(f"SELECT MAX(created_at) FROM {table}")
                            last_update = cur.fetchone()[0]
                            if last_update:
                                print(f"         Último registro: {last_update}")
                    except Exception as e:
                        print(f"      ❌ Error consultando {table}: {e}")
    except Exception as e:
        print(f"   ❌ Error conectando a PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
print()

# 5. Probar parsing de CSVs
print("5️⃣ TEST DE PARSING DE CSVs")
print("-" * 80)
try:
    from jobs.booknetic_export_improved import parse_csv_file, map_customers_to_db, map_appointments_to_db, map_payments_to_db
    
    # Test customers
    customers_files = sorted(downloads_dir.glob("customers_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if customers_files:
        print(f"   📋 Parseando {customers_files[0].name}...")
        rows = parse_csv_file(customers_files[0])
        print(f"      Raw rows: {len(rows)}")
        mapped = map_customers_to_db(rows)
        print(f"      Mapped rows: {len(mapped)}")
        if mapped:
            print(f"      Ejemplo de primer registro:")
            first = mapped[0]
            for key, value in list(first.items())[:5]:  # Mostrar solo primeros 5 campos
                print(f"         {key}: {value}")
    
    # Test appointments
    appointments_files = sorted(downloads_dir.glob("appointments_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if appointments_files:
        print(f"   📋 Parseando {appointments_files[0].name}...")
        rows = parse_csv_file(appointments_files[0])
        print(f"      Raw rows: {len(rows)}")
        mapped = map_appointments_to_db(rows)
        print(f"      Mapped rows: {len(mapped)}")
        if mapped:
            print(f"      Ejemplo de primer registro:")
            first = mapped[0]
            for key, value in list(first.items())[:5]:
                print(f"         {key}: {value}")
    
    print()
    
except Exception as e:
    print(f"   ❌ Error en parsing: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("🏁 DIAGNÓSTICO COMPLETO")
print("=" * 80)
print()
print("📝 POSIBLES PROBLEMAS:")
print()
print("   1. Si los CSVs están descargándose pero PostgreSQL no se actualiza:")
print("      - Verifica que DATABASE_URL esté configurado correctamente")
print("      - Revisa que el job realmente esté ejecutándose (logs)")
print("      - Confirma que replace_all() se esté llamando")
print()
print("   2. Si los CSVs NO se están descargando:")
print("      - Verifica BOOKNETIC_USERNAME/PASSWORD")
print("      - Revisa si Selenium está funcionando correctamente")
print("      - Mira los logs de errores del driver")
print()
print("   3. Si los registros en PostgreSQL no cambian:")
print("      - Verifica que los CSVs tengan datos NUEVOS")
print("      - Confirma que TRUNCATE + INSERT se está ejecutando")
print("      - Revisa si hay errores silenciosos en los logs")
print()


