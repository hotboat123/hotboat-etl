"""
Script rápido para probar que todo funciona
"""
import os
from pathlib import Path

print("=" * 80)
print("🚀 TEST RÁPIDO DE BOOKNETIC")
print("=" * 80)
print()

print("Selecciona qué quieres hacer:")
print()
print("1. 📥 Descargar CSVs frescos de Booknetic (toma ~2 minutos)")
print("2. 📤 Cargar CSVs existentes a PostgreSQL de Railway")
print("3. 🔄 Ambos: Descargar + Cargar")
print("4. 🔍 Solo diagnóstico (ver estado actual)")
print()

opcion = input("Opción (1-4): ").strip()

if opcion == "1":
    print()
    print("📥 Descargando CSVs frescos...")
    print()
    os.system("python jobs/booknetic_export_improved.py")
    
elif opcion == "2":
    print()
    print("📤 Cargando CSVs a PostgreSQL...")
    print()
    
    # Verificar que existen CSVs
    downloads_dir = Path("downloads")
    csv_files = list(downloads_dir.glob("*.csv"))
    
    if not csv_files:
        print("❌ No hay archivos CSV en downloads/")
        print("   Ejecuta primero la opción 1 para descargar")
        exit(1)
    
    print(f"✅ Encontrados {len(csv_files)} archivos CSV")
    print()
    
    # Ejecutar carga
    os.system("python test_with_railway.py")
    
elif opcion == "3":
    print()
    print("🔄 Descargando y cargando...")
    print()
    
    # Configurar variables de entorno
    print("⚙️  Configurando variables de entorno...")
    os.environ["DATABASE_URL"] = "postgresql://postgres:CxNTjRZqVQnUTzHUUeOYUITfqGWBXKVv@autorack.proxy.rlwy.net:31093/railway"
    os.environ["BOOKNETIC_USERNAME"] = "hotboatvillarrica@gmail.com"
    os.environ["BOOKNETIC_PASSWORD"] = "Hotboat777"
    
    print("✅ Variables configuradas")
    print()
    
    # Descargar
    print("📥 Paso 1: Descargando CSVs...")
    os.system("python jobs/booknetic_export_improved.py")
    
    print()
    print("📤 Paso 2: Cargando a PostgreSQL...")
    os.system("python test_with_railway.py")
    
elif opcion == "4":
    print()
    print("🔍 Ejecutando diagnóstico...")
    print()
    os.system("python diagnose_booknetic.py")
    
else:
    print()
    print("❌ Opción inválida")
    exit(1)

print()
print("=" * 80)
print("✅ PROCESO COMPLETADO")
print("=" * 80)
print()
print("💡 Próximos pasos:")
print()
print("   • Verifica los datos: python check_database.py")
print("   • Revisa los CSVs: dir downloads")
print("   • Ve los logs: railway logs (si estás en Railway)")
print()


