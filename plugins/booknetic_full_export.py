"""
Plugin para exportar datos completos de Booknetic (customers, appointments, payments)
usando Selenium y cargando a PostgreSQL.

Compatible con Railway - usa el script mejorado.
"""
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

def fetch() -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch all Booknetic data using Selenium export
    Returns: dict with keys 'customers', 'appointments', 'payments'
    """
    try:
        # Import the improved export script
        from jobs.booknetic_export_improved import (
            setup_chrome_driver,
            login_wordpress,
            navigate_to_booknetic,
            export_customers_data,
            export_appointments_data,
            export_payments_data,
            load_csv_to_database,
            parse_csv_file,
            map_customers_to_db,
            map_appointments_to_db,
            map_payments_to_db,
            find_latest_csv
        )
        
        print("[booknetic_full_export] Iniciando exportación completa...")
        
        # Get credentials
        username = os.getenv("BOOKNETIC_USERNAME")
        password = os.getenv("BOOKNETIC_PASSWORD")
        
        if not username or not password:
            raise RuntimeError("BOOKNETIC_USERNAME/PASSWORD not set")
        
        # Setup downloads directory
        downloads_dir = Path(os.getcwd()) / "downloads"
        downloads_dir.mkdir(exist_ok=True)
        
        # Setup driver
        driver = setup_chrome_driver()
        if not driver:
            raise RuntimeError("Failed to setup Chrome driver")
        
        try:
            # Verificar que las credenciales estén configuradas
            if not username:
                print("[booknetic_full_export] ❌ ERROR: BOOKNETIC_USERNAME no está configurado")
                raise RuntimeError("BOOKNETIC_USERNAME not set")
            
            if not password:
                print("[booknetic_full_export] ❌ ERROR: BOOKNETIC_PASSWORD no está configurado")
                raise RuntimeError("BOOKNETIC_PASSWORD not set")
            
            print(f"[booknetic_full_export] Usuario configurado: {username}")
            
            # Login
            print("[booknetic_full_export] Intentando login...")
            if not login_wordpress(driver, username, password):
                print("[booknetic_full_export] ❌ Login falló")
                print("[booknetic_full_export] Verifica:")
                print("  1. BOOKNETIC_USERNAME está correcto")
                print("  2. BOOKNETIC_PASSWORD está correcto")
                print("  3. El sitio web está accesible")
                print("  4. No hay bloqueos de IP o CAPTCHA")
                raise RuntimeError("Login failed - check credentials and site accessibility")
            
            # Navigate to Booknetic
            if not navigate_to_booknetic(driver):
                raise RuntimeError("Failed to navigate to Booknetic")
            
            # Export all data - ahora con verificación de descarga
            print("[booknetic_full_export] Exportando customers...")
            customers_success = export_customers_data(driver)
            if customers_success:
                print("[booknetic_full_export] ✅ Customers descargado correctamente")
            else:
                print("[booknetic_full_export] ⚠️  Advertencia: no se verificó la descarga de customers")
            time.sleep(2)
            
            print("[booknetic_full_export] Exportando appointments...")
            appointments_success = export_appointments_data(driver)
            if appointments_success:
                print("[booknetic_full_export] ✅ Appointments descargado correctamente")
            else:
                print("[booknetic_full_export] ⚠️  Advertencia: no se verificó la descarga de appointments")
            time.sleep(2)
            
            print("[booknetic_full_export] Exportando payments...")
            payments_success = export_payments_data(driver)
            if payments_success:
                print("[booknetic_full_export] ✅ Payments descargado correctamente")
            else:
                print("[booknetic_full_export] ⚠️  Advertencia: no se verificó la descarga de payments")
            time.sleep(2)
            
        finally:
            driver.quit()
        
        # Wait a bit more for downloads to complete (especialmente en Railway/headless)
        print("[booknetic_full_export] Esperando que terminen todas las descargas...")
        time.sleep(5)  # Aumentado de 3 a 5 segundos
        
        # Parse downloaded CSVs - usar archivos MÁS RECIENTES
        print("[booknetic_full_export] Procesando archivos CSV...")
        print(f"[booknetic_full_export] Buscando archivos en: {downloads_dir.absolute()}")
        
        customers = []
        appointments = []
        payments = []
        
        # Load customers - usar el archivo MÁS RECIENTE
        customers_file = find_latest_csv(downloads_dir, "customers_*.csv")
        if customers_file:
            print(f"[booknetic_full_export] Usando archivo customers: {customers_file.name}")
            rows = parse_csv_file(customers_file)
            customers = map_customers_to_db(rows)
            print(f"[booknetic_full_export] ✅ {len(customers)} customers procesados")
        else:
            print("[booknetic_full_export] ⚠️  No se encontró archivo de customers")
        
        # Load appointments - usar el archivo MÁS RECIENTE
        appointments_file = find_latest_csv(downloads_dir, "appointments_*.csv")
        if appointments_file:
            print(f"[booknetic_full_export] Usando archivo appointments: {appointments_file.name}")
            rows = parse_csv_file(appointments_file)
            appointments = map_appointments_to_db(rows)
            print(f"[booknetic_full_export] ✅ {len(appointments)} appointments procesados")
        else:
            print("[booknetic_full_export] ⚠️  No se encontró archivo de appointments")
        
        # Load payments - usar el archivo MÁS RECIENTE
        payments_file = find_latest_csv(downloads_dir, "payments_*.csv")
        if payments_file:
            print(f"[booknetic_full_export] Usando archivo payments: {payments_file.name}")
            rows = parse_csv_file(payments_file)
            payments = map_payments_to_db(rows)
            print(f"[booknetic_full_export] ✅ {len(payments)} payments procesados")
        else:
            print("[booknetic_full_export] ⚠️  No se encontró archivo de payments")
        
        print(f"[booknetic_full_export] Total exportado: {len(customers)} customers, {len(appointments)} appointments, {len(payments)} payments")
        
        return {
            "customers": customers,
            "appointments": appointments,
            "payments": payments
        }
        
    except Exception as e:
        print(f"[booknetic_full_export] Error: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError("booknetic_full_export failed") from e

