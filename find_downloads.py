"""
Script para verificar dónde están los archivos descargados de Booknetic
"""
import os
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("🔍 BUSCANDO ARCHIVOS CSV DE BOOKNETIC")
print("=" * 80)
print()

# 1. Verificar carpeta actual
current_dir = Path.cwd()
print(f"📂 Directorio actual: {current_dir}")
print()

# 2. Verificar carpeta downloads en el proyecto
downloads_dir = current_dir / "downloads"
print(f"📁 Carpeta downloads del proyecto: {downloads_dir}")
print(f"   ¿Existe? {'✅ SÍ' if downloads_dir.exists() else '❌ NO'}")

if downloads_dir.exists():
    csv_files = sorted(downloads_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if csv_files:
        print(f"   ✅ Encontrados {len(csv_files)} archivos CSV")
        print()
        print("   📋 ARCHIVOS MÁS RECIENTES:")
        for i, file in enumerate(csv_files[:10]):
            stat = file.stat()
            size = stat.st_size / 1024  # KB
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age_hours = (datetime.now() - mtime).total_seconds() / 3600
            
            time_marker = ""
            if age_hours < 1:
                time_marker = "🆕 RECIÉN DESCARGADO"
            elif age_hours < 24:
                time_marker = f"⏰ Hace {age_hours:.1f} horas"
            else:
                time_marker = f"📅 Hace {age_hours/24:.1f} días"
            
            print(f"   [{i+1}] {file.name}")
            print(f"       Ruta completa: {file.absolute()}")
            print(f"       Tamaño: {size:.1f} KB")
            print(f"       Modificado: {mtime.strftime('%Y-%m-%d %H:%M:%S')} - {time_marker}")
            print()
    else:
        print("   ⚠️ NO hay archivos CSV en esta carpeta")
print()

# 3. Verificar carpeta de descargas del usuario
user_downloads = Path.home() / "Downloads"
print(f"📁 Carpeta de descargas del usuario: {user_downloads}")
print(f"   ¿Existe? {'✅ SÍ' if user_downloads.exists() else '❌ NO'}")

if user_downloads.exists():
    # Buscar CSVs de Booknetic (con nombre específico)
    patterns = ["*customers*.csv", "*appointments*.csv", "*payments*.csv", "*booknetic*.csv"]
    found_files = []
    
    for pattern in patterns:
        found_files.extend(user_downloads.glob(pattern))
    
    if found_files:
        # Ordenar por fecha de modificación
        found_files = sorted(found_files, key=lambda p: p.stat().st_mtime, reverse=True)
        print(f"   ✅ Encontrados {len(found_files)} archivos relacionados con Booknetic")
        print()
        print("   📋 ARCHIVOS RELACIONADOS:")
        for i, file in enumerate(found_files[:5]):
            stat = file.stat()
            size = stat.st_size / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age_hours = (datetime.now() - mtime).total_seconds() / 3600
            
            time_marker = ""
            if age_hours < 1:
                time_marker = "🆕 RECIÉN DESCARGADO"
            elif age_hours < 24:
                time_marker = f"⏰ Hace {age_hours:.1f} horas"
            else:
                time_marker = f"📅 Hace {age_hours/24:.1f} días"
            
            print(f"   [{i+1}] {file.name}")
            print(f"       Ruta completa: {file.absolute()}")
            print(f"       Tamaño: {size:.1f} KB")
            print(f"       Modificado: {mtime.strftime('%Y-%m-%d %H:%M:%S')} - {time_marker}")
            print()
    else:
        print("   ℹ️ NO hay archivos de Booknetic en la carpeta de descargas del usuario")
print()

# 4. Mostrar carpeta configurada en el script
script_download_path = os.path.join(os.getcwd(), "downloads")
print(f"📁 Carpeta configurada en booknetic_export_improved.py:")
print(f"   {script_download_path}")
print(f"   ¿Existe? {'✅ SÍ' if os.path.exists(script_download_path) else '❌ NO'}")
print()

# 5. Verificar variables de entorno de Chrome
print("🔧 CONFIGURACIÓN DE CHROME:")
print("-" * 80)
# En Windows, Chrome suele guardar sus descargas en una de estas ubicaciones
possible_chrome_dirs = [
    Path.home() / "Downloads",
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Downloads",
    current_dir / "downloads"
]

print("   Posibles ubicaciones de descarga de Chrome:")
for i, loc in enumerate(possible_chrome_dirs):
    exists = "✅" if loc.exists() else "❌"
    print(f"   [{i+1}] {exists} {loc}")
print()

# 6. Instrucciones
print("=" * 80)
print("💡 CONCLUSIONES Y PRÓXIMOS PASOS")
print("=" * 80)
print()

if csv_files and csv_files[0].stat().st_mtime > (datetime.now().timestamp() - 3600):
    print("✅ LOS ARCHIVOS SE ESTÁN DESCARGANDO CORRECTAMENTE")
    print()
    print("Los archivos CSV están en:")
    print(f"   📂 {downloads_dir.absolute()}")
    print()
    print("Si esperabas verlos en otro lugar, es porque:")
    print("   • El script usa la carpeta 'downloads' dentro del proyecto")
    print("   • NO usa la carpeta de descargas predeterminada del navegador")
    print()
    print("Para cargar estos archivos a PostgreSQL, ejecuta:")
    print("   python test_with_railway.py")
else:
    print("⚠️ LOS ARCHIVOS NO ESTÁN ACTUALIZADOS")
    print()
    print("Los archivos en downloads/ no son recientes.")
    print("Esto podría significar que:")
    print("   • El script no se está ejecutando correctamente")
    print("   • Chrome está bloqueando las descargas")
    print("   • Los archivos se están descargando a otra ubicación")
    print()
    print("Para diagnosticar el problema, ejecuta:")
    print("   python diagnose_booknetic.py")
print()


