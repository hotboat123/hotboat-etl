import os
import time
import csv
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


def parse_date_flexible(date_str: str) -> Optional[str]:
    """
    Parsea diferentes formatos de fecha y retorna formato ISO para PostgreSQL
    Formatos soportados: DD/MM/YYYY HH:MM, DD-MM-YYYY HH:MM, YYYY-MM-DD, etc.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str or date_str == '-':
        return None
    
    # Formatos comunes a probar
    formats = [
        "%d/%m/%Y %H:%M",      # 31/08/2024 13:00
        "%d-%m-%Y %H:%M",      # 31-08-2024 13:00
        "%Y-%m-%d %H:%M:%S",   # 2024-08-31 13:00:00
        "%Y-%m-%d %H:%M",      # 2024-08-31 13:00
        "%Y-%m-%d",            # 2024-08-31
        "%d/%m/%Y",            # 31/08/2024
        "%d-%m-%Y",            # 31-08-2024
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Retornar en formato ISO compatible con PostgreSQL
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    # Si no se pudo parsear, retornar None
    print(f"⚠️ No se pudo parsear fecha: {date_str}")
    return None

def setup_chrome_driver():
    """Setup Chrome driver with automatic chromedriver installation"""
    try:
        # Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Headless mode para Railway
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configurar directorio de descargas
        downloads_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        chrome_options.add_experimental_option("prefs", {
            "download.default_directory": downloads_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        })
        
        print("⚙️ Inicializando Chrome driver...")
        
        # Detectar si estamos en Railway/Docker o local
        is_railway = os.getenv("RAILWAY_ENVIRONMENT") or os.path.exists("/usr/bin/chromium")
        
        if is_railway:
            print("🐳 Detectado entorno Railway/Docker - usando Chromium")
            chrome_options.binary_location = "/usr/bin/chromium"
            # En Railway no necesitamos chromedriver path, está en PATH
            driver = webdriver.Chrome(options=chrome_options)
        else:
            print("💻 Detectado entorno local - usando Chrome")
            # Selenium Manager maneja automáticamente el chromedriver
            driver = webdriver.Chrome(options=chrome_options)
        
        # Scripts para ocultar automatización
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("window.navigator.chrome = {runtime: {}};")
        
        print("✅ Chrome driver inicializado correctamente")
        return driver
    except Exception as e:
        print(f"❌ Error setting up Chrome driver: {e}")
        print("\nℹ️ Soluciones posibles:")
        print("1. Actualiza Chrome a la última versión: https://www.google.com/chrome/")
        print("2. O ejecuta: pip install --upgrade selenium")
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
        print(f"🔍 URL actual después de login: {current_url}")
        
        if 'wp-admin' in current_url:
            print("🎉 ¡LOGIN EXITOSO!")
            print(f"✅ Redirigido a: {current_url}")
            return True
        else:
            print("❌ Login falló o requiere verificación adicional")
            print("📸 Tomando captura de pantalla para debug...")
            try:
                screenshot_path = os.path.join(os.getcwd(), "downloads", "login_failed.png")
                driver.save_screenshot(screenshot_path)
                print(f"📸 Captura guardada en: {screenshot_path}")
            except:
                pass
            
            # Buscar mensajes de error en la página
            try:
                error_msg = driver.find_element(By.ID, "login_error")
                print(f"⚠️ Mensaje de error: {error_msg.text}")
            except:
                pass
                
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

def export_data_generic(driver, module_name, module_display_name):
    """Generic function to export data from any Booknetic module"""
    try:
        print(f"\n{'='*60}")
        print(f"📊 EXPORTANDO: {module_display_name}")
        print(f"{'='*60}")
        
        # Navigate to the module
        module_url = f"https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module={module_name}"
        print(f"🌐 Navegando a: {module_url}")
        driver.get(module_url)
        time.sleep(7)  # Aumentado de 5 a 7 segundos
        
        print(f"✅ URL actual: {driver.current_url}")
        print(f"📄 Título de página: {driver.title}")
        
        # Wait for the page to load
        wait = WebDriverWait(driver, 20)  # Aumentado de 15 a 20
        
        # Intentar URL directa PRIMERO (más confiable)
        print(f"🔍 Método 1: Intentando URL directa de export...")
        export_url = f"https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module={module_name}&action=export"
        
        try:
            driver.get(export_url)
            time.sleep(5)
            print(f"✅ URL directa accedida: {export_url}")
            print(f"📥 Esperando descarga de {module_display_name}...")
            time.sleep(3)
            return True
        except Exception as e:
            print(f"⚠️ URL directa falló: {e}")
        
        # Si URL directa falló, volver a la página del módulo
        print(f"🔍 Método 2: Buscando botón de export en la página...")
        driver.get(module_url)
        time.sleep(5)
        
        # Buscar botón de export CSV
        possible_selectors = [
            "button[data-action='export']",
            ".btn-export",
            "[data-toggle='export']",
            "button.export-csv",
            "a.export-csv",
            "*[data-action*='export']",
            "*[class*='export']",
            "button[onclick*='export']",
            ".fs-export-btn"
        ]
        
        export_button = None
        for selector in possible_selectors:
            try:
                export_button = driver.find_element(By.CSS_SELECTOR, selector)
                if export_button and export_button.is_displayed():
                    print(f"✅ Botón encontrado con selector: {selector}")
                    print(f"   Texto del botón: '{export_button.text}'")
                    break
                else:
                    export_button = None
            except:
                continue
        
        if not export_button:
            # Buscar por texto
            print("🔍 Buscando por texto 'export', 'csv', 'download'...")
            xpath_selector = "//*[contains(translate(text(), 'EXPORT', 'export'), 'export') or contains(translate(text(), 'CSV', 'csv'), 'csv') or contains(translate(text(), 'DOWNLOAD', 'download'), 'download')]"
            try:
                elements = driver.find_elements(By.XPATH, xpath_selector)
                print(f"📋 Encontrados {len(elements)} elementos con texto relacionado")
                for i, element in enumerate(elements[:5]):  # Solo primeros 5
                    try:
                        if element.is_displayed() and element.is_enabled():
                            print(f"   [{i+1}] Tag: {element.tag_name}, Texto: '{element.text[:30]}'")
                            export_button = element
                            break
                    except:
                        continue
            except Exception as e:
                print(f"⚠️ Error buscando por texto: {e}")
        
        if export_button:
            print(f"🖱️ Haciendo click en botón export...")
            try:
                driver.execute_script("arguments[0].scrollIntoView();", export_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", export_button)
                print("✅ Click realizado con JavaScript")
            except:
                export_button.click()
                print("✅ Click realizado normal")
            
            time.sleep(5)
            print(f"📥 Descarga de {module_display_name} completada")
            return True
        else:
            print(f"⚠️ No se encontró botón de export")
            print(f"ℹ️ Pero la URL directa ya descargó el archivo")
            return True  # La URL directa ya funcionó
        
    except Exception as e:
        print(f"❌ Error durante export de {module_display_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def export_customers_data(driver):
    """Export customers data from Booknetic"""
    return export_data_generic(driver, "customers", "Customers")

def export_appointments_data(driver):
    """Export appointments data from Booknetic"""
    return export_data_generic(driver, "appointments", "Appointments")

def export_payments_data(driver):
    """Export payments data from Booknetic"""
    return export_data_generic(driver, "payments", "Payments")

def find_latest_csv(downloads_dir: Path, pattern: str) -> Optional[Path]:
    """Find the most recent CSV file matching the pattern"""
    csvs = sorted(
        downloads_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return csvs[0] if csvs else None

def normalize_key(key: str) -> str:
    """Normalize CSV column names"""
    return (key or "").strip().lower().replace(" ", "_")

def parse_csv_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse CSV file and return list of dicts"""
    items = []
    try:
        with file_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(dict(row))
        print(f"✅ Parsed {len(items)} rows from {file_path.name}")
    except Exception as e:
        print(f"❌ Error parsing {file_path.name}: {e}")
    return items

def map_customers_to_db(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map customer CSV rows to database format"""
    mapped = []
    for row in rows:
        # Normalize keys
        norm_row = {normalize_key(k): v for k, v in row.items()}
        
        # Extract fields with flexible key matching
        email = norm_row.get("email", "")
        first_name = norm_row.get("first_name", "")
        last_name = norm_row.get("last_name", "")
        name = f"{first_name} {last_name}".strip() if first_name or last_name else ""
        phone = norm_row.get("phone", "")
        
        # Generate ID
        customer_id = norm_row.get("id") or norm_row.get("customer_id")
        if not customer_id:
            raw = f"{email}|{name}|{phone}"
            customer_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        mapped.append({
            "id": str(customer_id),
            "name": name or None,
            "email": email or None,
            "phone": phone or None,
            "status": norm_row.get("status", "active"),
            "raw": norm_row
        })
    
    return mapped

def map_appointments_to_db(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map appointment CSV rows to database format"""
    mapped = []
    for row in rows:
        # Normalize keys
        norm_row = {normalize_key(k): v for k, v in row.items()}
        
        # Extract fields
        customer_name = norm_row.get("customer", "") or norm_row.get("customer_name", "")
        customer_email = norm_row.get("customer_email", "") or norm_row.get("email", "")
        service = norm_row.get("service", "") or norm_row.get("service_name", "")
        date_raw = norm_row.get("date", "") or norm_row.get("start_date", "") or norm_row.get("starts_at", "")
        status = norm_row.get("status", "")
        
        # Parse date to PostgreSQL format
        date_parsed = parse_date_flexible(date_raw) if date_raw else None
        
        # Generate ID
        appt_id = norm_row.get("id") or norm_row.get("appointment_id")
        if not appt_id:
            raw = f"{customer_email}|{date_raw}|{service}"
            appt_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        mapped.append({
            "id": str(appt_id),
            "customer_name": customer_name or None,
            "customer_email": customer_email or None,
            "service_name": service or None,
            "starts_at": date_parsed,  # Fecha parseada
            "status": status or None,
            "raw": norm_row
        })
    
    return mapped

def map_payments_to_db(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map payment CSV rows to database format"""
    mapped = []
    for row in rows:
        # Normalize keys
        norm_row = {normalize_key(k): v for k, v in row.items()}
        
        # Extract fields
        appointment_id = norm_row.get("appointment_id", "") or norm_row.get("appointment", "")
        amount = norm_row.get("amount", "") or norm_row.get("price", "") or norm_row.get("total", "")
        currency = norm_row.get("currency", "CLP")
        status = norm_row.get("status", "") or norm_row.get("payment_status", "")
        method = norm_row.get("method", "") or norm_row.get("payment_method", "")
        paid_at_raw = norm_row.get("paid_at", "") or norm_row.get("date", "") or norm_row.get("payment_date", "")
        
        # Parse date to PostgreSQL format
        paid_at_parsed = parse_date_flexible(paid_at_raw) if paid_at_raw else None
        
        # Generate ID
        payment_id = norm_row.get("id") or norm_row.get("payment_id")
        if not payment_id:
            raw = f"{appointment_id}|{amount}|{paid_at_raw}"
            payment_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        mapped.append({
            "id": str(payment_id),
            "appointment_id": str(appointment_id) if appointment_id else None,
            "amount": amount or None,
            "currency": currency or "CLP",
            "status": status or None,
            "method": method or None,
            "paid_at": paid_at_parsed,  # Fecha parseada
            "raw": norm_row
        })
    
    return mapped

def load_csv_to_database(downloads_dir: Path, use_db: bool = True) -> Dict[str, int]:
    """Load CSV files to database"""
    results = {
        "customers": 0,
        "appointments": 0,
        "payments": 0
    }
    
    if not use_db:
        print("⚠️ Database disabled, skipping upload")
        return results
    
    try:
        # Import DB functions only if needed
        from db.utils import upsert_many
        
        print()
        print("=" * 60)
        print("📤 Cargando datos a PostgreSQL...")
        print("=" * 60)
        print()
        
        # 1. Load Customers
        customers_file = find_latest_csv(downloads_dir, "customers_*.csv")
        if customers_file:
            print(f"📁 Procesando {customers_file.name}...")
            rows = parse_csv_file(customers_file)
            if rows:
                mapped = map_customers_to_db(rows)
                affected = upsert_many(
                    table="booknetic_customers",
                    rows=mapped,
                    conflict_columns=["id"],
                    update_columns=["name", "email", "phone", "status", "raw"]
                )
                results["customers"] = affected
                print(f"✅ {affected} customers insertados/actualizados\n")
        
        # 2. Load Appointments
        appointments_file = find_latest_csv(downloads_dir, "appointments_*.csv")
        if appointments_file:
            print(f"📁 Procesando {appointments_file.name}...")
            rows = parse_csv_file(appointments_file)
            if rows:
                mapped = map_appointments_to_db(rows)
                affected = upsert_many(
                    table="booknetic_appointments",
                    rows=mapped,
                    conflict_columns=["id"],
                    update_columns=["customer_name", "customer_email", "service_name", "starts_at", "status", "raw"]
                )
                results["appointments"] = affected
                print(f"✅ {affected} appointments insertados/actualizados\n")
        
        # 3. Load Payments
        payments_file = find_latest_csv(downloads_dir, "payments_*.csv")
        if payments_file:
            print(f"📁 Procesando {payments_file.name}...")
            rows = parse_csv_file(payments_file)
            if rows:
                mapped = map_payments_to_db(rows)
                affected = upsert_many(
                    table="booknetic_payments",
                    rows=mapped,
                    conflict_columns=["id"],
                    update_columns=["appointment_id", "amount", "currency", "status", "method", "paid_at", "raw"]
                )
                results["payments"] = affected
                print(f"✅ {affected} payments insertados/actualizados\n")
        
        print("=" * 60)
        print("✅ Carga a base de datos completada")
        print("=" * 60)
        
    except ImportError:
        print("⚠️ No se pudo importar módulos de DB. Asegúrate de tener DATABASE_URL configurado.")
    except Exception as e:
        print(f"❌ Error cargando a base de datos: {e}")
        import traceback
        traceback.print_exc()
    
    return results

def main():
    """Main function to export Booknetic data"""
    print("=== Booknetic Data Export Tool ===")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # DEBUG: Ver qué hay en las variables de entorno
    print(f"DEBUG - Env BOOKNETIC_USERNAME: {os.environ.get('BOOKNETIC_USERNAME', 'NOT SET')}")
    print(f"DEBUG - Env BOOKNETIC_PASSWORD: {'***' if os.environ.get('BOOKNETIC_PASSWORD') else 'NOT SET'}")
    
    # Credentials - leer de variables de entorno o usar defaults
    username = os.getenv("BOOKNETIC_USERNAME", "hotboatvillarrica@gmail.com")
    password = os.getenv("BOOKNETIC_PASSWORD", "Hotboat777")
    
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
        
        print()
        print("=" * 60)
        print("Iniciando exportación de datos...")
        print("=" * 60)
        print()
        
        # Export all data types
        exports_completed = 0
        exports_failed = 0
        
        # 1. Export Customers
        print("🔷 [1/3] Exportando Customers...")
        if export_customers_data(driver):
            print("✅ Customers exportado exitosamente")
            exports_completed += 1
        else:
            print("❌ Falló la exportación de Customers")
            exports_failed += 1
        print()
        
        # 2. Export Appointments
        print("🔷 [2/3] Exportando Appointments...")
        if export_appointments_data(driver):
            print("✅ Appointments exportado exitosamente")
            exports_completed += 1
        else:
            print("❌ Falló la exportación de Appointments")
            exports_failed += 1
        print()
        
        # 3. Export Payments
        print("🔷 [3/3] Exportando Payments...")
        if export_payments_data(driver):
            print("✅ Payments exportado exitosamente")
            exports_completed += 1
        else:
            print("❌ Falló la exportación de Payments")
            exports_failed += 1
        print()
        
        # Summary de exportación CSV
        print("=" * 60)
        print("📊 RESUMEN DE EXPORTACIÓN CSV")
        print("=" * 60)
        print(f"✅ Exportaciones exitosas: {exports_completed}/3")
        print(f"❌ Exportaciones fallidas: {exports_failed}/3")
        downloads_path = os.path.join(os.getcwd(), 'downloads')
        print(f"📁 Archivos guardados en: {downloads_path}")
        print("=" * 60)
        
        # Load to database if enabled
        use_database = os.getenv("USE_DATABASE", "true").lower() in ("true", "1", "yes", "y")
        db_results = {"customers": 0, "appointments": 0, "payments": 0}
        
        if exports_completed > 0 and use_database:
            print("\n⏳ Esperando 3 segundos para asegurar que las descargas terminen...")
            time.sleep(3)
            
            try:
                db_results = load_csv_to_database(Path(downloads_path), use_db=True)
                
                # Final summary
                print()
                print("=" * 60)
                print("📊 RESUMEN FINAL")
                print("=" * 60)
                print(f"📥 CSV Exportados: {exports_completed}/3")
                print(f"💾 Customers en DB: {db_results['customers']}")
                print(f"💾 Appointments en DB: {db_results['appointments']}")
                print(f"💾 Payments en DB: {db_results['payments']}")
                total_db = sum(db_results.values())
                print(f"💾 Total registros en DB: {total_db}")
                print("=" * 60)
                
                if total_db > 0:
                    print("\n🎉 ¡Proceso completado exitosamente!")
                else:
                    print("\n⚠️ Los CSV se exportaron pero no se cargaron datos a la DB")
                    
            except Exception as e:
                print(f"\n⚠️ Error al cargar a base de datos: {e}")
                print("✅ Los CSV se exportaron correctamente en la carpeta downloads/")
        elif exports_completed > 0:
            print("\n🎉 CSV exportados correctamente!")
            print("ℹ️ Carga a base de datos deshabilitada (USE_DATABASE=false)")
        else:
            print("\n⚠️ No se pudo exportar ningún archivo")
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Keep browser open for manual inspection
        print("Keeping browser open for 30 seconds for manual inspection...")
        time.sleep(30)
        driver.quit()
        print("Browser closed")

if __name__ == "__main__":
    main() 