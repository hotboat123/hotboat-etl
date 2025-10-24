"""
Script para limpiar/reiniciar las tablas de la base de datos
Elimina todos los datos pero mantiene la estructura
"""
import os
import sys

# Agregar la raíz del proyecto al path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db.connection import get_connection


def reset_tables():
    """Limpia todas las tablas de datos"""
    
    print("=" * 60)
    print("🗑️  REINICIANDO BASE DE DATOS")
    print("=" * 60)
    print()
    
    # Confirmar con el usuario
    print("⚠️  ADVERTENCIA: Esto eliminará TODOS los datos de las siguientes tablas:")
    print("   - booknetic_customers")
    print("   - booknetic_appointments")
    print("   - booknetic_payments")
    print("   - job_runs")
    print()
    
    confirmacion = input("¿Estás seguro? Escribe 'SI' para continuar: ")
    
    if confirmacion.upper() != "SI":
        print("\n❌ Operación cancelada")
        return
    
    print("\n🔄 Limpiando tablas...")
    print()
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Limpiar tablas en orden (respetando foreign keys)
                tables = [
                    "booknetic_payments",
                    "booknetic_appointments", 
                    "booknetic_customers",
                    "job_runs"
                ]
                
                for table in tables:
                    try:
                        cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                        print(f"✅ {table} limpiada")
                    except Exception as e:
                        print(f"⚠️  {table}: {e}")
                
                conn.commit()
                
        print()
        print("=" * 60)
        print("✅ BASE DE DATOS REINICIADA EXITOSAMENTE")
        print("=" * 60)
        print()
        print("📊 Todas las tablas están ahora vacías y listas para nuevos datos")
        print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Error al reiniciar la base de datos: {e}")
        print("=" * 60)
        sys.exit(1)


def verify_clean():
    """Verifica que las tablas estén vacías"""
    print("🔍 Verificando que las tablas estén vacías...")
    print()
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                tables = [
                    "booknetic_customers",
                    "booknetic_appointments",
                    "booknetic_payments",
                    "job_runs"
                ]
                
                all_empty = True
                for table in tables:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    
                    if count == 0:
                        print(f"✅ {table}: {count} registros")
                    else:
                        print(f"⚠️  {table}: {count} registros (esperado: 0)")
                        all_empty = False
                
                print()
                if all_empty:
                    print("✅ Todas las tablas están vacías")
                else:
                    print("⚠️  Algunas tablas aún tienen datos")
                    
    except Exception as e:
        print(f"❌ Error al verificar: {e}")


if __name__ == "__main__":
    reset_tables()
    print()
    verify_clean()

