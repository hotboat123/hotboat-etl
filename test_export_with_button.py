"""
Script para probar la descarga haciendo click en el botón correcto
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
print("🧪 TEST DE DESCARGA CON EL BOTÓN CORRECTO")
print("=" * 80)
print()

# Configurar carpeta
downloads_dir = Path.cwd() / "downloads"
downloads_dir.mkdir(exist_ok=True)

# Contar archivos antes
csv_files_before = list(downloads_dir.glob("*.csv"))
print(f"📊 Archivos CSV ANTES: {len(csv_files_before)}")
print()

# Configurar Chrome
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

prefs = {
    "download.default_directory": str(downloads_dir.absolute()),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": False,
    "profile.default_content_setting_values.automatic_downloads": 1,
}
chrome_options.add_experimental_option("prefs", prefs)

print(f"📂 Descargas configuradas a: {downloads_dir.absolute()}")
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
    print("📥 DESCARGANDO CUSTOMERS")
    print("=" * 80)
    print()
    
    # Ir al módulo de customers
    customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers"
    print(f"🌐 Navegando a: {customers_url}")
    driver.get(customers_url)
    time.sleep(5)
    
    # Buscar el botón con el selector correcto
    print("🔍 Buscando botón 'EXPORT TO CSV'...")
    export_button = driver.find_element(By.CSS_SELECTOR, "button.export_csv")
    print(f"✅ Botón encontrado: '{export_button.text}'")
    
    # Scroll al botón
    driver.execute_script("arguments[0].scrollIntoView();", export_button)
    time.sleep(1)
    
    # Hacer click
    print("🖱️  Haciendo click en el botón...")
    driver.execute_script("arguments[0].click();", export_button)
    print("✅ Click realizado")
    
    # Esperar descarga
    print("⏳ Esperando descarga (15 segundos)...")
    time.sleep(15)
    
    # Verificar descarga
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
        # Verificar en Downloads del usuario
        user_downloads = Path.home() / "Downloads"
        user_files = sorted(user_downloads.glob("customers*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if user_files and (time.time() - user_files[0].stat().st_mtime) < 30:
            print(f"✅ Pero encontré un archivo reciente en Downloads del usuario:")
            print(f"   {user_files[0].name}")
            print(f"   Ubicación: {user_files[0]}")
            print()
            print("El archivo se descargó a la carpeta de descargas del usuario")
            print("en lugar de la carpeta del proyecto.")
    
    print()
    print("=" * 80)
    print("📥 DESCARGANDO APPOINTMENTS")
    print("=" * 80)
    print()
    
    # Ir al módulo de appointments
    appointments_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=appointments"
    print(f"🌐 Navegando a: {appointments_url}")
    driver.get(appointments_url)
    time.sleep(5)
    
    # Buscar y hacer click
    export_button = driver.find_element(By.CSS_SELECTOR, "button.export_csv")
    print(f"✅ Botón encontrado: '{export_button.text}'")
    driver.execute_script("arguments[0].scrollIntoView();", export_button)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", export_button)
    print("✅ Click realizado")
    print("⏳ Esperando descarga (15 segundos)...")
    time.sleep(15)
    
    print()
    print("=" * 80)
    print("📥 DESCARGANDO PAYMENTS")
    print("=" * 80)
    print()
    
    # Ir al módulo de payments
    payments_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=payments"
    print(f"🌐 Navegando a: {payments_url}")
    driver.get(payments_url)
    time.sleep(5)
    
    # Buscar y hacer click
    export_button = driver.find_element(By.CSS_SELECTOR, "button.export_csv")
    print(f"✅ Botón encontrado: '{export_button.text}'")
    driver.execute_script("arguments[0].scrollIntoView();", export_button)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", export_button)
    print("✅ Click realizado")
    print("⏳ Esperando descarga (15 segundos)...")
    time.sleep(15)
    
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
print("📊 RESUMEN FINAL")
print("=" * 80)
print()

csv_files_final = list(downloads_dir.glob("*.csv"))
nuevos = len(csv_files_final) - len(csv_files_before)

print(f"Archivos CSV ANTES: {len(csv_files_before)}")
print(f"Archivos CSV DESPUÉS: {len(csv_files_final)}")
print(f"Archivos NUEVOS: {nuevos}")
print()

if nuevos > 0:
    print("✅ ¡LA DESCARGA FUNCIONÓ!")
    print()
    print("Archivos descargados:")
    for file in sorted(csv_files_final, key=lambda p: p.stat().st_mtime, reverse=True)[:nuevos]:
        print(f"   📄 {file.name}")
    print()
    print("Ahora puedes cargarlos a PostgreSQL con:")
    print("   python test_with_railway.py")
else:
    print("❌ NO SE DESCARGARON ARCHIVOS A LA CARPETA DEL PROYECTO")
    print()
    print("Verifica si se descargaron a:")
    print(f"   📂 {Path.home() / 'Downloads'}")
print()


