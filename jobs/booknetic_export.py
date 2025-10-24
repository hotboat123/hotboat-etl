#!/usr/bin/env python3
"""
Script para hacer login en WordPress y exportar datos de Booknetic (appointments y customers)
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from dotenv import load_dotenv
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# Cargar variables de entorno
load_dotenv()

def setup_chrome():
    """Configurar Chrome con configuraciones optimizadas"""
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Directorio temporal para Chrome: {temp_dir}")
    
    chrome_options = Options()
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    
    # Configurar directorio de datos de usuario temporal
    chrome_options.add_argument(f'--user-data-dir={temp_dir}')
    chrome_options.add_argument('--profile-directory=Default')
    
    # Configuraciones ultra permisivas para cookies
    chrome_options.add_argument('--enable-cookies')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-cross-origin-auth-prompt')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--disable-site-isolation-trials')
    chrome_options.add_argument('--disable-features=BlockInsecurePrivateNetworkRequests')
    
    # Configuraciones para evitar detección de bot
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Configuraciones de cookies muy permisivas
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values": {
            "cookies": 1,
            "images": 1,
            "javascript": 1,
            "plugins": 1,
            "popups": 0,
            "geolocation": 0,
            "notifications": 0,
            "media_stream": 0,
        },
        "profile.content_settings.exceptions.cookies": {
            "*": {"setting": 1},
            "https://hotboatchile.com": {"setting": 1},
            "http://hotboatchile.com": {"setting": 1}
        },
        "profile.cookie_controls_mode": 0,
        "profile.block_third_party_cookies": False,
        # Descargar directo a carpeta de inputs de reservas
        "download.default_directory": os.path.join(os.getcwd(), "archivos_input", "Archivos input reservas"),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    
    # User agent realista
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Headless control via env
    headless = os.getenv("HEADLESS", "true").strip().lower() in {"1", "true", "yes", "y"}
    if headless:
        try:
            chrome_options.add_argument("--headless=new")
        except Exception:
            chrome_options.add_argument("--headless")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Scripts para ocultar automatización
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_script("window.navigator.chrome = {runtime: {}};")
    driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});")
    driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});")
    
    driver.set_page_load_timeout(30)
    
    return driver, temp_dir

def login_wordpress(driver):
    """Hacer login en WordPress"""
    url = os.getenv('BOOKNETIC_URL')
    username = os.getenv('BOOKNETIC_USERNAME')
    password = os.getenv('BOOKNETIC_PASSWORD')
    
    print(f"🚀 Intentando login en: {url}")
    print(f"👤 Usuario: {username}")
    
    # PASO 1: Visitar página principal para establecer cookies básicas
    print("🌐 Visitando página principal para establecer cookies...")
    main_url = "https://hotboatchile.com"
    driver.get(main_url)
    time.sleep(3)
    
    # Establecer cookies manualmente
    print("🍪 Estableciendo cookies manualmente...")
    cookies_to_add = [
        {"name": "wp_test", "value": "test_value", "domain": ".hotboatchile.com"},
        {"name": "wordpress_test_cookie", "value": "WP Cookie check", "domain": ".hotboatchile.com"},
        {"name": "wp-settings-time-1", "value": str(int(time.time())), "domain": ".hotboatchile.com"},
    ]
    
    for cookie in cookies_to_add:
        try:
            driver.add_cookie(cookie)
            print(f"✅ Cookie añadida: {cookie['name']}")
        except Exception as e:
            print(f"⚠️ No se pudo añadir cookie {cookie['name']}: {e}")
    
    # PASO 2: Navegar al login
    print("📂 Navegando a la página de login...")
    driver.get(url)
    time.sleep(5)
    
    print("✍️ Rellenando formulario...")
    
    # Esperar a que los campos estén disponibles
    wait = WebDriverWait(driver, 10)
    
    # Rellenar usuario
    username_field = wait.until(EC.element_to_be_clickable((By.ID, "user_login")))
    username_field.clear()
    time.sleep(0.5)
    username_field.send_keys(username)
    print("✅ Usuario completado")
    
    # Rellenar contraseña
    password_field = driver.find_element(By.ID, "user_pass")
    password_field.clear()
    time.sleep(0.5)
    password_field.send_keys(password)
    print("✅ Contraseña completada")
    
    # Verificar Jetpack Protect
    try:
        jetpack_field = driver.find_element(By.ID, "jetpack_protect_answer")
        jetpack_field.clear()
        time.sleep(0.5)
        jetpack_field.send_keys("17")  # Suma fija: 9 + 8 = 17
        print("✅ Jetpack Protect completado (9 + 8 = 17)")
    except:
        print("✅ Jetpack Protect está desactivado")
    
    # Establecer cookies adicionales antes del login
    try:
        driver.execute_script("""
            document.cookie = 'wordpress_logged_in_test=active; path=/; domain=.hotboatchile.com';
            document.cookie = 'wp-settings-1=' + Math.floor(Date.now()/1000) + '; path=/; domain=.hotboatchile.com';
            document.cookie = 'wp-settings-time-1=' + Math.floor(Date.now()/1000) + '; path=/; domain=.hotboatchile.com';
        """)
        print("✅ Cookies adicionales establecidas")
    except Exception as e:
        print(f"⚠️ Error estableciendo cookies adicionales: {e}")
    
    # Hacer click en login
    print("🔐 Haciendo login...")
    login_button = driver.find_element(By.ID, "wp-submit")
    
    # Scroll y hacer visible
    driver.execute_script("arguments[0].scrollIntoView();", login_button)
    time.sleep(1)
    
    # Click usando JavaScript para evitar interceptaciones
    driver.execute_script("arguments[0].click();", login_button)
    
    # Esperar resultado
    print("⏳ Esperando resultado...")
    time.sleep(10)
    
    # Verificar resultado
    current_url = driver.current_url
    if 'wp-admin' in current_url:
        print("🎉 ¡LOGIN EXITOSO!")
        print(f"✅ Redirigido a: {current_url}")
        return True
    else:
        print("❌ Login falló")
        return False

def export_appointments(driver):
    """Exportar appointments desde Booknetic"""
    print("\n📅 === EXPORTANDO APPOINTMENTS ===")
    
    try:
        # Navegar a appointments
        appointments_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=appointments"
        print(f"📊 Navegando a appointments: {appointments_url}")
        driver.get(appointments_url)
        time.sleep(5)
        
        print(f"🔄 URL actual: {driver.current_url}")
        print(f"📄 Título: {driver.title}")
        
        # Buscar botón de export CSV
        wait = WebDriverWait(driver, 15)
        
        # Intentar diferentes selectores para el botón export
        possible_selectors = [
            "button[data-action='export']",
            "button:contains('Export')",
            "a:contains('Export')",
            ".btn-export",
            "[data-toggle='export']",
            "button.export-csv",
            "a.export-csv",
            "*[data-action*='export']",
            "*[class*='export']",
            "button[onclick*='export']"
        ]
        
        export_button = None
        for selector in possible_selectors:
            try:
                if ':contains' in selector:
                    # Para selectores con :contains, usar XPath
                    xpath_selector = f"//*[contains(text(), 'Export') or contains(text(), 'export') or contains(text(), 'CSV')]"
                    export_button = driver.find_element(By.XPATH, xpath_selector)
                else:
                    export_button = driver.find_element(By.CSS_SELECTOR, selector)
                
                if export_button and export_button.is_displayed():
                    print(f"✅ Botón export encontrado con selector: {selector}")
                    break
            except:
                continue
        
        if not export_button:
            # Buscar todos los botones y links visibles
            print("🔍 Buscando todos los botones y enlaces visibles...")
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            
            for element in all_buttons + all_links:
                try:
                    text = element.text.lower()
                    if 'export' in text or 'csv' in text or 'download' in text:
                        print(f"📋 Elemento encontrado: '{element.text}' - Tag: {element.tag_name}")
                        export_button = element
                        break
                except:
                    continue
        
        if export_button:
            print("📥 Haciendo click en botón de export...")
            driver.execute_script("arguments[0].scrollIntoView();", export_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", export_button)
            time.sleep(6)
            print("✅ Export de appointments iniciado")
        else:
            print("⚠️ No se encontró botón de export para appointments")
            
            # Mostrar el HTML de la página para debugging
            print("🔍 Mostrando elementos disponibles en la página...")
            try:
                # Buscar elementos que contengan 'export', 'csv', 'download'
                elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'export') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'csv') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]")
                for elem in elements[:10]:  # Solo los primeros 10
                    print(f"   - {elem.tag_name}: '{elem.text.strip()}'")
            except:
                pass
        
        return export_button is not None
        
    except Exception as e:
        print(f"❌ Error exportando appointments: {e}")
        return False

def export_customers(driver):
    """Exportar customers desde Booknetic"""
    print("\n👥 === EXPORTANDO CUSTOMERS ===")
    
    try:
        # Navegar a customers
        customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers"
        print(f"📊 Navegando a customers: {customers_url}")
        driver.get(customers_url)
        time.sleep(5)
        
        print(f"🔄 URL actual: {driver.current_url}")
        print(f"📄 Título: {driver.title}")
        
        # Buscar botón de export CSV (similar a appointments)
        wait = WebDriverWait(driver, 15)
        
        # Intentar diferentes selectores para el botón export
        possible_selectors = [
            "button[data-action='export']",
            "button:contains('Export')",
            "a:contains('Export')",
            ".btn-export",
            "[data-toggle='export']",
            "button.export-csv",
            "a.export-csv",
            "*[data-action*='export']",
            "*[class*='export']",
            "button[onclick*='export']"
        ]
        
        export_button = None
        for selector in possible_selectors:
            try:
                if ':contains' in selector:
                    # Para selectores con :contains, usar XPath
                    xpath_selector = f"//*[contains(text(), 'Export') or contains(text(), 'export') or contains(text(), 'CSV')]"
                    export_button = driver.find_element(By.XPATH, xpath_selector)
                else:
                    export_button = driver.find_element(By.CSS_SELECTOR, selector)
                
                if export_button and export_button.is_displayed():
                    print(f"✅ Botón export encontrado con selector: {selector}")
                    break
            except:
                continue
        
        if not export_button:
            # Buscar todos los botones y links visibles
            print("🔍 Buscando todos los botones y enlaces visibles...")
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            
            for element in all_buttons + all_links:
                try:
                    text = element.text.lower()
                    if 'export' in text or 'csv' in text or 'download' in text:
                        print(f"📋 Elemento encontrado: '{element.text}' - Tag: {element.tag_name}")
                        export_button = element
                        break
                except:
                    continue
        
        if export_button:
            print("📥 Haciendo click en botón de export...")
            driver.execute_script("arguments[0].scrollIntoView();", export_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", export_button)
            time.sleep(5)
            print("✅ Export de customers iniciado")
        else:
            print("⚠️ No se encontró botón de export para customers")
            
            # Mostrar el HTML de la página para debugging
            print("🔍 Mostrando elementos disponibles en la página...")
            try:
                # Buscar elementos que contengan 'export', 'csv', 'download'
                elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'export') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'csv') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]")
                for elem in elements[:10]:  # Solo los primeros 10
                    print(f"   - {elem.tag_name}: '{elem.text.strip()}'")
            except:
                pass
        
        return export_button is not None
        
    except Exception as e:
        print(f"❌ Error exportando customers: {e}")
        return False

def export_payments(driver):
    """Exportar payments desde Booknetic"""
    print("\n💳 === EXPORTANDO PAYMENTS ===")
    try:
        payments_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=payments"
        print(f"📊 Navegando a payments: {payments_url}")
        driver.get(payments_url)
        time.sleep(5)

        print(f"🔄 URL actual: {driver.current_url}")
        print(f"📄 Título: {driver.title}")

        wait = WebDriverWait(driver, 15)

        possible_selectors = [
            "button[data-action='export']",
            "button:contains('Export')",
            "a:contains('Export')",
            ".btn-export",
            "[data-toggle='export']",
            "button.export-csv",
            "a.export-csv",
            "*[data-action*='export']",
            "*[class*='export']",
            "button[onclick*='export']"
        ]

        export_button = None
        for selector in possible_selectors:
            try:
                if ':contains' in selector:
                    xpath_selector = f"//*[contains(text(), 'Export') or contains(text(), 'export') or contains(text(), 'CSV')]"
                    export_button = driver.find_element(By.XPATH, xpath_selector)
                else:
                    export_button = driver.find_element(By.CSS_SELECTOR, selector)
                if export_button and export_button.is_displayed():
                    print(f"✅ Botón export encontrado con selector: {selector}")
                    break
            except:
                continue

        if not export_button:
            print("🔍 Buscando todos los botones y enlaces visibles...")
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            for element in all_buttons + all_links:
                try:
                    text = element.text.lower()
                    if 'export' in text or 'csv' in text or 'download' in text:
                        print(f"📋 Elemento encontrado: '{element.text}' - Tag: {element.tag_name}")
                        export_button = element
                        break
                except:
                    continue

        if export_button:
            print("📥 Haciendo click en botón de export (payments)...")
            driver.execute_script("arguments[0].scrollIntoView();", export_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", export_button)
            time.sleep(6)
            print("✅ Export de payments iniciado")
        else:
            print("⚠️ No se encontró botón de export para payments")
            try:
                elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'export') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'csv') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]")
                for elem in elements[:10]:
                    print(f"   - {elem.tag_name}: '{elem.text.strip()}'")
            except:
                pass

        return export_button is not None
    except Exception as e:
        print(f"❌ Error exportando payments: {e}")
        return False

def wait_for_new_csv(download_dir: str, start_time: float, timeout: int = 60) -> str:
    """Espera hasta encontrar un CSV nuevo en download_dir modificado luego de start_time.
    Devuelve la ruta del archivo o cadena vacía si no aparece."""
    folder = Path(download_dir)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            csvs = sorted(
                [p for p in folder.glob('*.csv') if p.stat().st_mtime >= start_time],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if csvs:
                return str(csvs[0])
        except Exception:
            pass
        time.sleep(1)
    return ""

def main():
    """Función principal"""
    print("🚀 === BOOKNETIC DATA EXPORTER ===\n")
    
    # Directorio de descargas = carpeta de inputs de reservas
    downloads_dir = os.path.join(os.getcwd(), "archivos_input", "Archivos input reservas")
    os.makedirs(downloads_dir, exist_ok=True)
    print(f"📁 Directorio de descargas: {downloads_dir}")
    
    driver, temp_dir = setup_chrome()
    
    try:
        # 1. Login
        if not login_wordpress(driver):
            print("❌ Login falló, abortando...")
            return
        
        print("\n⏳ Esperando 5 segundos antes de proceder con las exportaciones...")
        time.sleep(5)
        
        # 2. Exportar appointments
        t0 = time.time()
        appointments_success = export_appointments(driver)
        appo_file = ""
        if appointments_success:
            appo_file = wait_for_new_csv(downloads_dir, t0, timeout=90)
            if appo_file:
                try:
                    today = datetime.now().strftime('%Y%m%d')
                    target = os.path.join(downloads_dir, f"appointments_{today}.csv")
                    # Si ya existe, agregar sufijo horario
                    if os.path.exists(target):
                        target = os.path.join(downloads_dir, f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                    os.replace(appo_file, target)
                    print(f"💾 Appointments guardado como: {target}")
                    appo_file = target
                except Exception as e:
                    print(f"⚠️ No se pudo renombrar appointments: {e}")
        
        print("\n⏳ Esperando 5 segundos entre exportaciones...")
        time.sleep(5)
        
        # 3. Exportar payments
        t1 = time.time()
        payments_success = export_payments(driver)
        pay_file = ""
        if payments_success:
            pay_file = wait_for_new_csv(downloads_dir, t1, timeout=90)
            if pay_file:
                try:
                    today = datetime.now().strftime('%Y%m%d')
                    target = os.path.join(downloads_dir, f"payments_{today}.csv")
                    if os.path.exists(target):
                        target = os.path.join(downloads_dir, f"payments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                    os.replace(pay_file, target)
                    print(f"💾 Payments guardado como: {target}")
                    pay_file = target
                except Exception as e:
                    print(f"⚠️ No se pudo renombrar payments: {e}")
        
        # Resumen
        print("\n" + "="*50)
        print("📊 RESUMEN DE EXPORTACIONES:")
        print(f"   📅 Appointments: {'✅ ÉXITO' if appointments_success else '❌ FALLO'}")
        print(f"   💳 Payments:    {'✅ ÉXITO' if payments_success else '❌ FALLO'}")
        
        if appointments_success and appo_file:
            print(f"   ↳ Archivo: {appo_file}")
        if payments_success and pay_file:
            print(f"   ↳ Archivo: {pay_file}")
        print("="*50)
        
        if appointments_success or payments_success:
            print(f"\n📁 Revisa el directorio de descargas: {downloads_dir}")
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cierre no interactivo para uso en CI / Actions
        
        if driver:
            driver.quit()
        
        # Limpiar directorio temporal
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 Directorio temporal limpiado: {temp_dir}")
        except:
            pass

if __name__ == "__main__":
    main() 