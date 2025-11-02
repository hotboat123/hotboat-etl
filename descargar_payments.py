"""
Script rápido para descargar SOLO payments
"""
import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

print("=" * 80)
print("📥 DESCARGANDO PAYMENTS")
print("=" * 80)
print()

# Configurar descargas
downloads_dir = Path(os.getcwd()) / "downloads"
downloads_dir.mkdir(exist_ok=True)

# Verificar archivos ANTES
payments_antes = list(downloads_dir.glob("payments*.csv"))
tiempo_antes = max([f.stat().st_mtime for f in payments_antes] + [0])
print(f"📊 Archivos de payments ANTES: {len(payments_antes)}")
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

# Inicializar
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
    
    # Ir a payments
    payments_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=payments"
    print(f"🌐 Navegando a: {payments_url}")
    driver.get(payments_url)
    time.sleep(5)
    
    # Buscar botón
    print("🔍 Buscando botón 'EXPORT TO CSV'...")
    export_button = driver.find_element(By.CSS_SELECTOR, "button.export_csv")
    print(f"✅ Botón encontrado: '{export_button.text}'")
    
    # Scroll y click
    driver.execute_script("arguments[0].scrollIntoView(true);", export_button)
    time.sleep(1)
    
    print("🖱️  Haciendo click...")
    driver.execute_script("arguments[0].click();", export_button)
    
    # Verificar descarga
    print("⏳ Esperando descarga...")
    archivo_descargado = None
    
    for i in range(20):  # 20 segundos
        time.sleep(1)
        
        # Buscar archivos nuevos
        payments_ahora = list(downloads_dir.glob("payments*.csv"))
        nuevos = [f for f in payments_ahora if f.stat().st_mtime > tiempo_antes]
        
        if nuevos:
            # Ordenar por tiempo, tomar el más reciente
            archivo_descargado = sorted(nuevos, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            tiempo_archivo = archivo_descargado.stat().st_mtime
            edad = time.time() - tiempo_archivo
            
            if edad < 5:  # Si es de hace menos de 5 segundos
                print(f"✅ ARCHIVO DESCARGADO!")
                print(f"   Nombre: {archivo_descargado.name}")
                print(f"   Ruta: {archivo_descargado.absolute()}")
                print(f"   Tamaño: {archivo_descargado.stat().st_size / 1024:.1f} KB")
                break
        
        # Verificar si está descargando (.crdownload)
        crdownload = list(downloads_dir.glob("*.crdownload"))
        if crdownload:
            print(f"   [{i+1:2d}/20] Descargando...", end='\r')
        else:
            print(f"   [{i+1:2d}/20] Esperando...", end='\r')
    
    print()  # Nueva línea
    
    if not archivo_descargado:
        print("⚠️  No se detectó descarga en 20 segundos")
        print()
        print("Verificando si hay archivos nuevos...")
        payments_final = list(downloads_dir.glob("payments*.csv"))
        if len(payments_final) > len(payments_antes):
            latest = sorted(payments_final, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            print(f"   📄 Archivo más reciente: {latest.name}")
            print(f"   Modificado: {datetime.fromtimestamp(latest.stat().st_mtime)}")
    
    print()
    print("⏸️  Navegador abierto 5 segundos...")
    time.sleep(5)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()

print()
print("✅ Completado")

