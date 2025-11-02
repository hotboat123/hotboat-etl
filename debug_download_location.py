"""
Script para debuggear exactamente dónde se están descargando los archivos CSV
"""
import os
import time
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

print("=" * 80)
print("🐛 DEBUG: DÓNDE SE DESCARGAN LOS CSV")
print("=" * 80)
print()

# Directorio configurado en el código
downloads_dir = Path(os.getcwd()) / "downloads"
downloads_dir.mkdir(exist_ok=True)

print(f"📂 Directorio configurado en el código:")
print(f"   {downloads_dir.absolute()}")
print()

# Contar archivos ANTES
print("📊 Estado ANTES de la descarga:")
csv_before = list(downloads_dir.glob("*.csv"))
print(f"   Archivos CSV en {downloads_dir.name}: {len(csv_before)}")

user_downloads = Path.home() / "Downloads"
user_csv_before = list(user_downloads.glob("customers*.csv"))
print(f"   Archivos en Downloads del usuario: {len(user_csv_before)}")
print()

# Configurar Chrome con logs de descarga
chrome_options = Options()
# NO USAR HEADLESS para poder ver
# chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

# IMPORTANTE: Configurar directorio de descargas
prefs = {
    "download.default_directory": str(downloads_dir.absolute()),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": False,
    "profile.default_content_setting_values.automatic_downloads": 1,
}
chrome_options.add_experimental_option("prefs", prefs)

# Habilitar logging para ver mensajes de Chrome
chrome_options.add_argument("--enable-logging")
chrome_options.add_argument("--v=1")

print("⚙️  Configuración de Chrome:")
print(f"   download.default_directory: {str(downloads_dir.absolute())}")
print(f"   download.prompt_for_download: False")
print()

# Inicializar driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    # Login
    from jobs.booknetic_export_improved import login_wordpress, navigate_to_booknetic
    
    username = os.getenv("BOOKNETIC_USERNAME", "hotboatvillarrica@gmail.com")
    password = os.getenv("BOOKNETIC_PASSWORD", "Hotboat777")
    
    print("🔐 Haciendo login...")
    if not login_wordpress(driver, username, password):
        driver.quit()
        exit(1)
    
    if not navigate_to_booknetic(driver):
        driver.quit()
        exit(1)
    
    print()
    print("=" * 80)
    print("🔍 VERIFICANDO CONFIGURACIÓN DEL NAVEGADOR")
    print("=" * 80)
    print()
    
    # Verificar la configuración de descargas desde JavaScript
    download_path = driver.execute_script("""
        return navigator.userAgent;
    """)
    print(f"User Agent: {download_path}")
    
    # Navegar a la página de customers
    customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers"
    print(f"🌐 Navegando a: {customers_url}")
    driver.get(customers_url)
    time.sleep(5)
    
    # Screenshot ANTES del click
    screenshot_before = "debug_before_download.png"
    driver.save_screenshot(screenshot_before)
    print(f"📸 Screenshot guardado: {screenshot_before}")
    print()
    
    # Buscar botón
    print("🔍 Buscando botón 'EXPORT TO CSV'...")
    try:
        export_button = driver.find_element(By.CSS_SELECTOR, "button.export_csv")
        print(f"✅ Botón encontrado: '{export_button.text}'")
        print(f"   Clase: {export_button.get_attribute('class')}")
        print(f"   Visible: {export_button.is_displayed()}")
        print(f"   Habilitado: {export_button.is_enabled()}")
    except Exception as e:
        print(f"❌ No se encontró el botón: {e}")
        driver.quit()
        exit(1)
    
    print()
    print("🖱️  Haciendo click en el botón...")
    
    # Scroll al botón
    driver.execute_script("arguments[0].scrollIntoView(true);", export_button)
    time.sleep(1)
    
    # Click
    driver.execute_script("arguments[0].click();", export_button)
    print("✅ Click realizado")
    print()
    
    # Monitorear descargas en tiempo real
    print("⏳ Monitoreando descargas en tiempo real...")
    print("-" * 80)
    
    for i in range(15):  # Monitorear por 15 segundos
        time.sleep(1)
        
        # Verificar en directorio configurado
        csv_now = list(downloads_dir.glob("*.csv"))
        new_in_project = len(csv_now) - len(csv_before)
        
        # Verificar en Downloads del usuario
        user_csv_now = list(user_downloads.glob("customers*.csv"))
        new_in_user = len(user_csv_now) - len(user_csv_before)
        
        # Verificar archivos temporales (.crdownload = descarga en progreso)
        crdownload_files = list(downloads_dir.glob("*.crdownload"))
        user_crdownload = list(user_downloads.glob("*.crdownload"))
        
        status = f"[{i+1:2d}s]"
        
        if new_in_project > 0:
            status += f" ✅ {new_in_project} nuevo(s) en {downloads_dir.name}"
            print(status)
            break
        elif new_in_user > 0:
            status += f" ⚠️  {new_in_user} nuevo(s) en Downloads del usuario"
            print(status)
            break
        elif crdownload_files:
            status += f" ⏬ Descargando en {downloads_dir.name}..."
            print(status, end='\r')
        elif user_crdownload:
            status += f" ⏬ Descargando en Downloads del usuario..."
            print(status, end='\r')
        else:
            status += f" ⏳ Esperando... (proyecto:{new_in_project}, usuario:{new_in_user})"
            print(status, end='\r')
    
    print()
    print("-" * 80)
    print()
    
    # Screenshot DESPUÉS del click
    screenshot_after = "debug_after_download.png"
    driver.save_screenshot(screenshot_after)
    print(f"📸 Screenshot guardado: {screenshot_after}")
    print()
    
    # Verificar resultado final
    print("📊 Estado DESPUÉS de la descarga:")
    print()
    
    csv_after = list(downloads_dir.glob("*.csv"))
    new_files_project = set(csv_after) - set(csv_before)
    
    user_csv_after = list(user_downloads.glob("customers*.csv"))
    new_files_user = set(user_csv_after) - set(user_csv_before)
    
    if new_files_project:
        print(f"✅ ARCHIVOS DESCARGADOS EN {downloads_dir.name}:")
        for file in new_files_project:
            stat = file.stat()
            size = stat.st_size / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"   📄 {file.name}")
            print(f"      Ruta: {file.absolute()}")
            print(f"      Tamaño: {size:.1f} KB")
            print(f"      Creado: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"❌ NO se descargaron archivos en {downloads_dir.name}")
    
    print()
    
    if new_files_user:
        print(f"⚠️  ARCHIVOS DESCARGADOS EN Downloads del usuario:")
        for file in new_files_user:
            stat = file.stat()
            size = stat.st_size / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime)
            if (datetime.now() - mtime).total_seconds() < 30:
                print(f"   📄 {file.name}")
                print(f"      Ruta: {file.absolute()}")
                print(f"      Tamaño: {size:.1f} KB")
                print(f"      Creado: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print()
    print("⏸️  Navegador permanecerá abierto 10 segundos...")
    time.sleep(10)
    
except KeyboardInterrupt:
    print("\n⚠️  Interrumpido")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("\n🔚 Cerrando Chrome...")
    driver.quit()

print()
print("=" * 80)
print("💡 DIAGNÓSTICO")
print("=" * 80)
print()

csv_final = list(downloads_dir.glob("*.csv"))
user_csv_final = list(user_downloads.glob("customers*.csv"))

if len(csv_final) > len(csv_before):
    print("✅ LOS ARCHIVOS SE DESCARGAN CORRECTAMENTE")
    print(f"   Ubicación: {downloads_dir.absolute()}")
    print()
    print("El código está funcionando bien.")
elif len([f for f in user_csv_final if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() < 30]) > 0:
    print("⚠️  LOS ARCHIVOS SE DESCARGAN PERO EN OTRA UBICACIÓN")
    print(f"   Se descargan en: {user_downloads}")
    print(f"   Deberían descargarse en: {downloads_dir.absolute()}")
    print()
    print("💡 SOLUCIÓN:")
    print("   Chrome en modo visible ignora la configuración de descargas.")
    print("   Necesitas usar modo headless o mover los archivos manualmente.")
    print()
    print("   Para mover los archivos:")
    print(f"   move \"{user_downloads}\\customers*.csv\" \"{downloads_dir}\"")
    print(f"   move \"{user_downloads}\\appointments*.csv\" \"{downloads_dir}\"")
    print(f"   move \"{user_downloads}\\payments*.csv\" \"{downloads_dir}\"")
else:
    print("❌ NO SE DESCARGÓ NINGÚN ARCHIVO")
    print()
    print("Posibles problemas:")
    print("   1. El botón no descarga, solo muestra algo")
    print("   2. Requiere alguna acción adicional")
    print("   3. Chrome bloqueó la descarga")
    print()
    print("Revisa los screenshots:")
    print("   - debug_before_download.png")
    print("   - debug_after_download.png")
print()


