"""
Script para debuggear qué está pasando en la página de export de Booknetic
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
print("🐛 DEBUG DE BOOKNETIC EXPORT")
print("=" * 80)
print()

# Configurar carpeta
downloads_dir = Path.cwd() / "downloads"
downloads_dir.mkdir(exist_ok=True)

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
        print("❌ Login falló")
        driver.quit()
        exit(1)
    
    if not navigate_to_booknetic(driver):
        print("❌ No se pudo navegar a Booknetic")
        driver.quit()
        exit(1)
    
    print()
    print("=" * 80)
    print("🔍 ANALIZANDO PÁGINA DE CUSTOMERS")
    print("=" * 80)
    print()
    
    # Ir al módulo de customers
    customers_url = "https://hotboatchile.com/wp-admin/admin.php?page=booknetic&module=customers"
    print(f"🌐 Navegando a: {customers_url}")
    driver.get(customers_url)
    time.sleep(5)
    
    # Tomar screenshot
    screenshot_path = "debug_customers_page.png"
    driver.save_screenshot(screenshot_path)
    print(f"📸 Screenshot guardado en: {screenshot_path}")
    print()
    
    # Buscar todos los botones/enlaces relacionados con export
    print("🔍 Buscando elementos relacionados con 'export'...")
    print()
    
    # Buscar por diferentes selectores
    selectors = [
        ("CSS", "button[data-action='export']"),
        ("CSS", ".btn-export"),
        ("CSS", "[data-toggle='export']"),
        ("CSS", "button.export-csv"),
        ("CSS", "a.export-csv"),
        ("CSS", "*[data-action*='export']"),
        ("CSS", "*[class*='export']"),
        ("CSS", "button[onclick*='export']"),
        ("XPATH", "//*[contains(translate(text(), 'EXPORT', 'export'), 'export')]"),
        ("XPATH", "//*[contains(translate(text(), 'CSV', 'csv'), 'csv')]"),
        ("XPATH", "//*[contains(translate(text(), 'DOWNLOAD', 'download'), 'download')]"),
    ]
    
    found_elements = []
    for selector_type, selector in selectors:
        try:
            if selector_type == "CSS":
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            else:
                elements = driver.find_elements(By.XPATH, selector)
            
            for element in elements:
                if element.is_displayed():
                    info = {
                        'selector': selector,
                        'tag': element.tag_name,
                        'text': element.text[:50],
                        'class': element.get_attribute('class'),
                        'onclick': element.get_attribute('onclick'),
                        'href': element.get_attribute('href'),
                        'data-action': element.get_attribute('data-action'),
                    }
                    found_elements.append(info)
        except Exception as e:
            pass
    
    if found_elements:
        print(f"✅ Encontrados {len(found_elements)} elementos relacionados:")
        print()
        for i, elem in enumerate(found_elements, 1):
            print(f"[{i}] {elem['tag'].upper()}")
            print(f"    Selector: {elem['selector']}")
            if elem['text']:
                print(f"    Texto: '{elem['text']}'")
            if elem['class']:
                print(f"    Class: {elem['class']}")
            if elem['onclick']:
                print(f"    onclick: {elem['onclick'][:80]}")
            if elem['href']:
                print(f"    href: {elem['href']}")
            if elem['data-action']:
                print(f"    data-action: {elem['data-action']}")
            print()
    else:
        print("❌ No se encontraron elementos relacionados con export")
        print()
        print("Posibles razones:")
        print("   1. El botón está oculto o requiere scroll")
        print("   2. Se carga dinámicamente con JavaScript")
        print("   3. La interfaz cambió")
        print()
    
    # Obtener el HTML de la página (solo header)
    print("📄 HTML del header de la página:")
    print("-" * 80)
    try:
        # Buscar el contenedor principal
        main_content = driver.find_element(By.TAG_NAME, "body")
        html = main_content.get_attribute('innerHTML')
        
        # Buscar secciones que contengan "export" o "download"
        lines = html.split('\n')
        relevant_lines = [line for line in lines if 'export' in line.lower() or 'download' in line.lower() or 'csv' in line.lower()]
        
        if relevant_lines:
            print(f"Encontradas {len(relevant_lines)} líneas relevantes:")
            for i, line in enumerate(relevant_lines[:20], 1):  # Solo primeras 20
                print(f"{i}. {line.strip()[:150]}")
        else:
            print("No se encontraron líneas con 'export', 'download' o 'csv'")
    except Exception as e:
        print(f"Error obteniendo HTML: {e}")
    
    print()
    print("-" * 80)
    print()
    
    # Probar click en el primer elemento encontrado
    if found_elements:
        print("🖱️  Intentando hacer click en el primer elemento...")
        try:
            if selector_type == "CSS":
                element = driver.find_element(By.CSS_SELECTOR, found_elements[0]['selector'])
            else:
                element = driver.find_element(By.XPATH, found_elements[0]['selector'])
            
            driver.execute_script("arguments[0].scrollIntoView();", element)
            time.sleep(1)
            
            # Tomar screenshot antes del click
            driver.save_screenshot("debug_before_click.png")
            print("📸 Screenshot antes del click: debug_before_click.png")
            
            driver.execute_script("arguments[0].click();", element)
            print("✅ Click realizado")
            
            print("⏳ Esperando 10 segundos para ver si descarga...")
            time.sleep(10)
            
            # Tomar screenshot después del click
            driver.save_screenshot("debug_after_click.png")
            print("📸 Screenshot después del click: debug_after_click.png")
            
            # Verificar si se descargó algo
            csv_files = list(downloads_dir.glob("customers*.csv"))
            csv_files = sorted(csv_files, key=lambda p: p.stat().st_mtime, reverse=True)
            
            if csv_files:
                latest = csv_files[0]
                age_seconds = time.time() - latest.stat().st_mtime
                if age_seconds < 15:
                    print(f"✅ ¡ARCHIVO DESCARGADO! {latest.name}")
                else:
                    print(f"⚠️  El archivo más reciente es de hace {age_seconds:.0f} segundos")
            else:
                print("❌ No se descargó ningún archivo")
        except Exception as e:
            print(f"❌ Error haciendo click: {e}")
    
    print()
    print("⏸️  Navegador permanecerá abierto 20 segundos para inspección...")
    print("   Puedes inspeccionar las screenshots o presionar Ctrl+C")
    time.sleep(20)
    
except KeyboardInterrupt:
    print("\n⚠️  Interrumpido por el usuario")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("\n🔚 Cerrando Chrome...")
    driver.quit()
    print("✅ Chrome cerrado")

print()
print("=" * 80)
print("💡 PRÓXIMOS PASOS")
print("=" * 80)
print()
print("1. Revisa las screenshots:")
print("   - debug_customers_page.png")
print("   - debug_before_click.png (si se generó)")
print("   - debug_after_click.png (si se generó)")
print()
print("2. Revisa el output de arriba para ver qué elementos se encontraron")
print()
print("3. Si hay algún botón de export, anota su selector para actualizar el código")
print()


