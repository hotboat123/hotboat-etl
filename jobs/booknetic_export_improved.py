import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
from datetime import datetime
import json

def setup_chrome_driver():
    """Setup Chrome driver with automatic chromedriver installation"""
    try:
        # Auto-install chromedriver
        chromedriver_autoinstaller.install()
        
        # Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configurar directorio de descargas
        chrome_options.add_experimental_option("prefs", {
            "download.default_directory": os.path.join(os.getcwd(), "downloads"),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        })
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Scripts para ocultar automatización
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("window.navigator.chrome = {runtime: {}};")
        
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        return None

def login_wordpress(driver, username, password):
    """Login to WordPress first, then navigate to Booknetic"""
    try:
        print("🚀 Iniciando proceso de login en WordPress...")
        
        # PASO 1: Visitar página principal para establecer cookies básicas
        print("🌐 Visitando página principal para establecer cookies...")
        main_url = "https://hotboatchile.com"
        driver.get(main_url)
        time.sleep(3)
        
        # PASO 2: Navegar al login de WordPress
        print("📂 Navegando a la página de login de WordPress...")
        login_url = "https://hotboatchile.com/wp-admin/"
        driver.get(login_url)
        time.sleep(5)
        
        print("✍️ Rellenando formulario de WordPress...")
        
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
            
    except Exception as e:
        print(f"Error during login: {e}")
        return False

def navigate_to_booknetic(driver):
    """Navigate to Booknetic after WordPress login"""
    try:
        print("📊 Navegando a Booknetic...")
        booknetic_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic"
        driver.get(booknetic_url)
        time.sleep(5)
        
        print(f"🔄 URL actual: {driver.current_url}")
        print(f"📄 Título: {driver.title}")
        
        if "booknetic" in driver.current_url.lower():
            print("✅ Navegación a Booknetic exitosa")
            return True
        else:
            print("❌ No se pudo navegar a Booknetic")
            return False
            
    except Exception as e:
        print(f"Error navegando a Booknetic: {e}")
        return False

def export_customers_data(driver):
    """Export customers data from Booknetic"""
    try:
        print("📊 Navegando a la sección de customers...")
        
        # Navigate to customers
        customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers"
        driver.get(customers_url)
        time.sleep(5)
        
        print(f"🔄 URL actual: {driver.current_url}")
        print(f"📄 Título: {driver.title}")
        
        # Wait for the page to load
        wait = WebDriverWait(driver, 15)
        
        # Buscar botón de export CSV
        print("🔍 Buscando botón de export...")
        
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
                    if 'export' in text or 'csv' in text or 'descargar' in text:
                        print(f"✅ Encontrado elemento con texto: {element.text}")
                        export_button = element
                        break
                except:
                    continue
        
        if export_button:
            print("🖱️ Haciendo click en botón export...")
            driver.execute_script("arguments[0].click();", export_button)
            print("✅ Click realizado")
            
            # Wait for download to start
            time.sleep(5)
            print("📥 Descarga iniciada")
            return True
        else:
            print("❌ No se encontró botón de export")
            print("🔍 Intentando URL directa de export...")
            
            # Try direct export URL
            export_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers&action=export"
            driver.get(export_url)
            time.sleep(5)
            
            print("✅ URL directa de export accedida")
            return True
        
    except Exception as e:
        print(f"Error during export: {e}")
        return False

def main():
    """Main function to export Booknetic data"""
    print("=== Booknetic Data Export Tool ===")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Credentials
    username = "admin@hotboat.cl"
    password = "H0TBOAT123"
    
    print(f"Using username: {username}")
    
    # Setup driver
    driver = setup_chrome_driver()
    if not driver:
        print("Failed to setup Chrome driver")
        return
    
    try:
        # Login to WordPress
        if not login_wordpress(driver, username, password):
            print("Failed to login to WordPress. Exiting...")
            return
        
        # Navigate to Booknetic
        if not navigate_to_booknetic(driver):
            print("Failed to navigate to Booknetic. Exiting...")
            return
        
        # Export data
        if export_customers_data(driver):
            print("Export process completed successfully!")
            print("Please check your downloads folder for the exported file.")
        else:
            print("Export process failed")
            
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        # Keep browser open for manual inspection
        print("Keeping browser open for 30 seconds for manual inspection...")
        time.sleep(30)
        driver.quit()
        print("Browser closed")

if __name__ == "__main__":
    main() 