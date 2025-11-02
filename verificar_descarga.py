"""
Script para verificar exactamente dónde se descarga el archivo y si hay alguna variable que lo contenga
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
print("🔍 VERIFICACIÓN: ¿DÓNDE QUEDA EL ARCHIVO DESPUÉS DEL CLICK?")
print("=" * 80)
print()

# 1. Dónde está configurado
downloads_dir = Path(os.getcwd()) / "downloads"
downloads_dir.mkdir(exist_ok=True)

print("1️⃣ CONFIGURACIÓN DEL DIRECTORIO DE DESCARGA:")
print("-" * 80)
print(f"   Directorio configurado: {downloads_dir.absolute()}")
print(f"   ¿Existe? {'✅ SÍ' if downloads_dir.exists() else '❌ NO'}")
print()

# 2. Configurar Chrome
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

prefs = {
    "download.default_directory": str(downloads_dir.absolute()),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
}
chrome_options.add_experimental_option("prefs", prefs)

print("2️⃣ CONFIGURACIÓN DE CHROME:")
print("-" * 80)
print(f"   download.default_directory: {downloads_dir.absolute()}")
print()

# 3. Inicializar driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

print("3️⃣ VARIABLES DEL DRIVER:")
print("-" * 80)
print("   driver es de tipo:", type(driver).__name__)
print("   driver no tiene atributo para descargas descargadas")
print("   driver NO guarda la ruta del archivo en ninguna variable")
print()

# Verificar qué atributos tiene el driver relacionados con descargas
print("   Atributos del driver relacionados con 'download':")
driver_attrs = [attr for attr in dir(driver) if 'download' in attr.lower() or 'file' in attr.lower()]
if driver_attrs:
    for attr in driver_attrs[:10]:  # Primeros 10
        try:
            value = getattr(driver, attr)
            if not callable(value):
                print(f"      - {attr}: {type(value).__name__}")
        except:
            pass
else:
    print("      ⚠️  NO hay atributos relacionados con descargas")
print()

print("=" * 80)
print("✅ CONCLUSIÓN IMPORTANTE:")
print("=" * 80)
print()
print("❌ El driver NO guarda el archivo en ninguna variable")
print("✅ El archivo se descarga DIRECTAMENTE al sistema de archivos")
print("✅ La única forma de saber dónde está es VERIFICAR EL SISTEMA DE ARCHIVOS")
print()

# 4. Función para verificar después del click
def verificar_archivo_descargado(downloads_dir, pattern="*.csv", timeout=15):
    """
    Verifica si se descargó un archivo nuevo después del click
    
    RETORNA:
        Path | None: Ruta del archivo descargado, o None si no se encontró
    """
    # Guardar estado ANTES
    archivos_antes = set(downloads_dir.glob(pattern))
    tiempos_antes = {f: f.stat().st_mtime for f in archivos_antes}
    
    print("   📊 Estado ANTES del click:")
    print(f"      Archivos existentes: {len(archivos_antes)}")
    print()
    
    # Esperar y monitorear
    print("   ⏳ Monitoreando descargas...")
    tiempo_inicio = time.time()
    
    while time.time() - tiempo_inicio < timeout:
        time.sleep(0.5)  # Verificar cada medio segundo
        
        archivos_ahora = set(downloads_dir.glob(pattern))
        archivos_nuevos = archivos_ahora - archivos_antes
        
        # Verificar archivos .crdownload (descarga en progreso)
        crdownload = list(downloads_dir.glob("*.crdownload"))
        
        if archivos_nuevos:
            # Verificar que sea realmente nuevo (creado después del inicio)
            for archivo in archivos_nuevos:
                tiempo_archivo = archivo.stat().st_mtime
                if tiempo_archivo >= tiempo_inicio:
                    print(f"      ✅ ARCHIVO DESCARGADO: {archivo.name}")
                    return archivo
        
        if crdownload:
            print(f"      ⏬ Descargando... ({len(crdownload)} archivo(s) .crdownload)", end='\r')
        else:
            elapsed = int(time.time() - tiempo_inicio)
            print(f"      [{elapsed:2d}s] Esperando...", end='\r')
    
    print()  # Nueva línea después del \r
    return None

print("=" * 80)
print("4️⃣ PRUEBA REAL: Hacer click y verificar")
print("=" * 80)
print()

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
    
    # Ir a customers
    customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers"
    print(f"🌐 Navegando a: {customers_url}")
    driver.get(customers_url)
    time.sleep(5)
    
    # Buscar botón
    export_button = driver.find_element(By.CSS_SELECTOR, "button.export_csv")
    print(f"✅ Botón encontrado: '{export_button.text}'")
    print()
    
    # Verificar ANTES del click
    archivo_antes = list(downloads_dir.glob("customers*.csv"))
    tiempo_antes = max([f.stat().st_mtime for f in archivo_antes] + [0])
    print(f"📊 Archivos ANTES del click: {len(archivo_antes)}")
    print()
    
    # Hacer click
    print("🖱️  Haciendo click...")
    driver.execute_script("arguments[0].scrollIntoView(true);", export_button)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", export_button)
    print("✅ Click realizado")
    print()
    
    # Verificar DESPUÉS del click (esto es lo que necesitas)
    print("🔍 VERIFICANDO SISTEMA DE ARCHIVOS...")
    print("-" * 80)
    
    archivo_descargado = verificar_archivo_descargado(
        downloads_dir, 
        pattern="customers*.csv",
        timeout=20
    )
    
    print()
    
    if archivo_descargado:
        print("=" * 80)
        print("✅ RESULTADO:")
        print("=" * 80)
        print()
        print(f"📄 Archivo encontrado:")
        print(f"   Nombre: {archivo_descargado.name}")
        print(f"   Ruta completa: {archivo_descargado.absolute()}")
        print(f"   Tamaño: {archivo_descargado.stat().st_size / 1024:.1f} KB")
        print()
        print("⚠️  IMPORTANTE:")
        print("   - Este archivo NO está en ninguna variable del driver")
        print("   - Está SOLO en el sistema de archivos")
        print("   - Para accederlo, usa: Path(downloads_dir) / archivo_descargado.name")
        print()
    else:
        print("❌ No se encontró ningún archivo nuevo")
        print()
        print("Posibles causas:")
        print("   1. El archivo se descargó a otra ubicación (Downloads del usuario)")
        print("   2. Chrome bloqueó la descarga")
        print("   3. La descarga tomó más de 20 segundos")
        print()
        
        # Verificar en Downloads del usuario
        user_downloads = Path.home() / "Downloads"
        user_files = sorted(
            user_downloads.glob("customers*.csv"), 
            key=lambda p: p.stat().st_mtime, 
            reverse=True
        )
        if user_files:
            latest = user_files[0]
            age = time.time() - latest.stat().st_mtime
            if age < 30:
                print(f"⚠️  Encontrado archivo reciente en Downloads del usuario:")
                print(f"   {latest.name}")
                print(f"   Ruta: {latest.absolute()}")
    
    print()
    print("⏸️  Navegador abierto 5 segundos más...")
    time.sleep(5)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()

print()
print("=" * 80)
print("💡 CÓDIGO PARA AGREGAR A TU SCRIPT:")
print("=" * 80)
print()
print("""
# Después de hacer click en el botón, AGREGA ESTO:

def verificar_archivo_descargado(downloads_dir, pattern="*.csv", timeout=15):
    '''Verifica si se descargó un archivo nuevo después del click'''
    import time
    from pathlib import Path
    
    archivos_antes = set(Path(downloads_dir).glob(pattern))
    tiempo_inicio = time.time()
    
    while time.time() - tiempo_inicio < timeout:
        time.sleep(0.5)
        archivos_ahora = set(Path(downloads_dir).glob(pattern))
        archivos_nuevos = archivos_ahora - archivos_antes
        
        for archivo in archivos_nuevos:
            if archivo.stat().st_mtime >= tiempo_inicio:
                return archivo  # 👈 AQUÍ ESTÁ LA RUTA DEL ARCHIVO
    
    return None

# USO:
archivo_descargado = verificar_archivo_descargado(downloads_dir, "customers*.csv")
if archivo_descargado:
    print(f"✅ Archivo descargado: {archivo_descargado}")
    # Usar archivo_descargado para leer el CSV
else:
    print("❌ No se descargó el archivo")
""")
print()

