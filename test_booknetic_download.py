"""
Script para probar la descarga de Booknetic con visualización (sin headless)
para diagnosticar problemas de descarga
"""
import os
import time
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

print("=" * 80)
print("🧪 TEST DE DESCARGA DE BOOKNETIC (MODO VISIBLE)")
print("=" * 80)
print()

# Configurar carpeta de descargas
downloads_dir = Path.cwd() / "downloads"
downloads_dir.mkdir(exist_ok=True)

print(f"📂 Carpeta de descargas configurada: {downloads_dir.absolute()}")
print()

# Contar archivos antes
csv_files_before = list(downloads_dir.glob("*.csv"))
print(f"📊 Archivos CSV ANTES de la descarga: {len(csv_files_before)}")
print()

# Configurar Chrome
print("⚙️  Configurando Chrome...")
chrome_options = Options()

# ¡¡NO USAR HEADLESS!! Para poder ver qué pasa
# chrome_options.add_argument("--headless=new")  # COMENTADO

chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

# Configurar descargas
prefs = {
    "download.default_directory": str(downloads_dir.absolute()),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": False,  # Deshabilitar SafeBrowsing que puede bloquear descargas
    "profile.default_content_setting_values.automatic_downloads": 1,  # Permitir múltiples descargas
}
chrome_options.add_experimental_option("prefs", prefs)

print(f"✅ Descargas configuradas a: {downloads_dir.absolute()}")
print()

# Inicializar driver
print("🚀 Iniciando Chrome...")
try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("✅ Chrome iniciado correctamente (MODO VISIBLE)")
    print()
except Exception as e:
    print(f"❌ Error iniciando Chrome: {e}")
    exit(1)

try:
    # Login
    print("🔐 Iniciando login en WordPress...")
    username = os.getenv("BOOKNETIC_USERNAME", "hotboatvillarrica@gmail.com")
    password = os.getenv("BOOKNETIC_PASSWORD", "Hotboat777")
    
    print(f"   Usuario: {username}")
    
    # Import funciones del script principal
    from jobs.booknetic_export_improved import login_wordpress, navigate_to_booknetic
    
    if not login_wordpress(driver, username, password):
        print("❌ Login falló")
        driver.quit()
        exit(1)
    
    if not navigate_to_booknetic(driver):
        print("❌ No se pudo navegar a Booknetic")
        driver.quit()
        exit(1)
    
    print()
    print("=" * 80)
    print("📥 INICIANDO DESCARGA DE CUSTOMERS")
    print("=" * 80)
    print()
    
    # Probar descarga de customers
    customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers&action=export"
    print(f"🌐 Navegando a: {customers_url}")
    driver.get(customers_url)
    
    print("⏳ Esperando 10 segundos para que termine la descarga...")
    print("   (Puedes ver la ventana de Chrome para verificar que se está descargando)")
    time.sleep(10)
    
    # Verificar que se descargó
    csv_files_after = list(downloads_dir.glob("*.csv"))
    new_files = set(csv_files_after) - set(csv_files_before)
    
    if new_files:
        print()
        print("✅ ¡ARCHIVOS DESCARGADOS!")
        for file in new_files:
            stat = file.stat()
            size = stat.st_size / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"   📄 {file.name}")
            print(f"      Tamaño: {size:.1f} KB")
            print(f"      Modificado: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print()
        print("⚠️  NO SE DESCARGÓ NINGÚN ARCHIVO NUEVO")
        print()
        print("Verifica en la ventana de Chrome si:")
        print("   1. Apareció un diálogo de descarga")
        print("   2. Chrome bloqueó la descarga")
        print("   3. Se descargó a otra ubicación")
        print()
        print("También verifica en:")
        print(f"   📂 {Path.home() / 'Downloads'}")
    
    print()
    print("⏸️  El navegador permanecerá abierto 30 segundos para que puedas inspeccionar")
    print("   Presiona Ctrl+C para cerrar antes")
    time.sleep(30)
    
except KeyboardInterrupt:
    print()
    print("⚠️  Interrumpido por el usuario")
except Exception as e:
    print(f"❌ Error durante el test: {e}")
    import traceback
    traceback.print_exc()
finally:
    print()
    print("🔚 Cerrando Chrome...")
    driver.quit()
    print("✅ Chrome cerrado")

print()
print("=" * 80)
print("📊 RESUMEN FINAL")
print("=" * 80)
print()

# Contar archivos después
csv_files_final = list(downloads_dir.glob("*.csv"))
print(f"Archivos CSV ANTES: {len(csv_files_before)}")
print(f"Archivos CSV DESPUÉS: {len(csv_files_final)}")
print(f"Archivos NUEVOS: {len(csv_files_final) - len(csv_files_before)}")
print()

if len(csv_files_final) > len(csv_files_before):
    print("✅ LA DESCARGA FUNCIONÓ CORRECTAMENTE")
    print()
    print("Ahora puedes ejecutar el script en modo headless (automático):")
    print("   python jobs/booknetic_export_improved.py")
else:
    print("❌ LA DESCARGA NO FUNCIONÓ")
    print()
    print("Posibles problemas:")
    print("   1. Chrome bloqueó la descarga")
    print("   2. El sitio requiere interacción adicional")
    print("   3. La URL de export cambió")
    print("   4. Permisos de carpeta")
    print()
    print("Revisa si los archivos están en:")
    print(f"   📂 {Path.home() / 'Downloads'}")
print()


