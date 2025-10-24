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
            # Login
            if not login_wordpress(driver, username, password):
                raise RuntimeError("Login failed")
            
            # Navigate to Booknetic
            if not navigate_to_booknetic(driver):
                raise RuntimeError("Failed to navigate to Booknetic")
            
            # Export all data
            print("[booknetic_full_export] Exportando customers...")
            export_customers_data(driver)
            time.sleep(2)
            
            print("[booknetic_full_export] Exportando appointments...")
            export_appointments_data(driver)
            time.sleep(2)
            
            print("[booknetic_full_export] Exportando payments...")
            export_payments_data(driver)
            time.sleep(2)
            
        finally:
            driver.quit()
        
        # Wait for downloads to complete
        time.sleep(3)
        
        # Parse downloaded CSVs
        print("[booknetic_full_export] Procesando archivos CSV...")
        
        customers = []
        appointments = []
        payments = []
        
        # Load customers
        customers_file = find_latest_csv(downloads_dir, "customers_*.csv")
        if customers_file:
            rows = parse_csv_file(customers_file)
            customers = map_customers_to_db(rows)
            print(f"[booknetic_full_export] {len(customers)} customers procesados")
        
        # Load appointments
        appointments_file = find_latest_csv(downloads_dir, "appointments_*.csv")
        if appointments_file:
            rows = parse_csv_file(appointments_file)
            appointments = map_appointments_to_db(rows)
            print(f"[booknetic_full_export] {len(appointments)} appointments procesados")
        
        # Load payments
        payments_file = find_latest_csv(downloads_dir, "payments_*.csv")
        if payments_file:
            rows = parse_csv_file(payments_file)
            payments = map_payments_to_db(rows)
            print(f"[booknetic_full_export] {len(payments)} payments procesados")
        
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
        return {"customers": [], "appointments": [], "payments": []}

