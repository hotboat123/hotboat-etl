"""
Booknetic Export usando REQUESTS en lugar de Selenium
Mucho más rápido y confiable para Railway
"""
import os
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Database imports
from db.core import get_pool

# Configuración
BASE_URL = os.getenv("BOOKNETIC_URL", "https://hotboatchile.com")
USERNAME = os.getenv("BOOKNETIC_USERNAME", "")
PASSWORD = os.getenv("BOOKNETIC_PASSWORD", "")
DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"


def create_session_and_login() -> Optional[requests.Session]:
    """
    Crea una sesión de requests y hace login en WordPress
    """
    print("\n" + "="*60)
    print("🔐 INICIANDO LOGIN CON REQUESTS")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # Step 1: Get login page to get cookies and nonce
    print(f"📄 Obteniendo página de login...")
    login_page_url = f"{BASE_URL}/wp-login.php"
    
    try:
        response = session.get(login_page_url, timeout=30)
        print(f"✅ Página de login obtenida (status: {response.status_code})")
    except Exception as e:
        print(f"❌ Error obteniendo página de login: {e}")
        return None
    
    # Step 2: Login POST
    print(f"🔑 Enviando credenciales de login...")
    login_data = {
        'log': USERNAME,
        'pwd': PASSWORD,
        'wp-submit': 'Log In',
        'redirect_to': f"{BASE_URL}/wp-admin/",
        'testcookie': '1'
    }
    
    try:
        response = session.post(login_page_url, data=login_data, timeout=30, allow_redirects=True)
        print(f"📬 Respuesta de login (status: {response.status_code})")
        
        # Verificar si el login fue exitoso
        if 'wp-admin' in response.url or response.status_code == 200:
            # Verificar que no estemos en la página de login
            if 'wp-login.php' not in response.url:
                print(f"✅ Login exitoso!")
                print(f"   URL final: {response.url}")
                return session
            else:
                print(f"❌ Login falló - seguimos en wp-login.php")
                # Buscar mensaje de error
                soup = BeautifulSoup(response.text, 'html.parser')
                error_div = soup.find('div', {'id': 'login_error'})
                if error_div:
                    print(f"   Error: {error_div.get_text(strip=True)}")
                return None
        else:
            print(f"❌ Login falló - status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error durante login: {e}")
        return None


def download_csv(session: requests.Session, module_name: str, display_name: str) -> Optional[Path]:
    """
    Descarga el CSV de un módulo específico
    """
    print(f"\n{'='*60}")
    print(f"📥 DESCARGANDO: {display_name}")
    print(f"{'='*60}")
    
    # URL de export directo
    export_url = f"{BASE_URL}/wp-admin/admin.php?page=booknetic&module={module_name}&action=export"
    print(f"🌐 URL: {export_url}")
    
    try:
        # Hacer la petición de descarga
        response = session.get(export_url, timeout=60)
        print(f"📬 Respuesta (status: {response.status_code})")
        
        if response.status_code == 200:
            # Verificar que sea un CSV
            content_type = response.headers.get('Content-Type', '')
            print(f"📄 Content-Type: {content_type}")
            
            # Generar nombre de archivo
            today = datetime.now().strftime("%Y%b%d")
            filename = f"{module_name}_{today}.csv"
            filepath = DOWNLOADS_DIR / filename
            
            # Guardar el archivo
            filepath.write_bytes(response.content)
            file_size = len(response.content)
            print(f"✅ CSV guardado: {filename} ({file_size} bytes)")
            
            # Verificar contenido
            if file_size < 100:
                print(f"⚠️ Archivo muy pequeño - podría no ser válido")
                print(f"   Contenido: {response.text[:200]}")
            
            return filepath
        else:
            print(f"❌ Error descargando CSV - status: {response.status_code}")
            print(f"   Respuesta: {response.text[:500]}")
            return None
            
    except Exception as e:
        print(f"❌ Error durante descarga: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_latest_csv(module_name: str) -> Optional[Path]:
    """Encuentra el CSV más reciente para un módulo"""
    pattern = f"{module_name}_*.csv"
    csv_files = sorted(DOWNLOADS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return csv_files[0] if csv_files else None


def normalize_key(key: str) -> str:
    """Normaliza las claves de CSV"""
    return key.lower().strip().replace(" ", "_").replace("-", "_")


def parse_csv_file(filepath: Path) -> List[Dict[str, Any]]:
    """Parse CSV file"""
    import csv
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def parse_date_flexible(date_str: str) -> Optional[str]:
    """Parse diferentes formatos de fecha"""
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str or date_str == '-':
        return None
    
    formats = [
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    return None


def map_customers_to_db(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map customer CSV rows to database format"""
    mapped = []
    for row in rows:
        norm_row = {normalize_key(k): v for k, v in row.items()}
        
        customer_id = norm_row.get("id") or norm_row.get("customer_id")
        email = norm_row.get("email", "")
        name = norm_row.get("full_name", "") or norm_row.get("name", "")
        phone = norm_row.get("phone", "") or norm_row.get("phone_number", "")
        
        if not customer_id and email:
            customer_id = hashlib.sha1(email.encode("utf-8")).hexdigest()[:16]
        
        mapped.append({
            "id": str(customer_id),
            "name": name or None,
            "email": email or None,
            "phone": phone or None,
            "raw": norm_row
        })
    
    return mapped


def map_appointments_to_db(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map appointment CSV rows to database format"""
    mapped = []
    for row in rows:
        norm_row = {normalize_key(k): v for k, v in row.items()}
        
        customer_name = norm_row.get("customer", "") or norm_row.get("customer_name", "")
        customer_email = norm_row.get("customer_email", "") or norm_row.get("email", "")
        service = norm_row.get("service", "") or norm_row.get("service_name", "")
        date_raw = norm_row.get("date", "") or norm_row.get("start_date", "") or norm_row.get("starts_at", "")
        status = norm_row.get("status", "")
        
        date_parsed = parse_date_flexible(date_raw) if date_raw else None
        
        appt_id = norm_row.get("id") or norm_row.get("appointment_id")
        if not appt_id:
            raw = f"{customer_email}|{date_raw}|{service}"
            appt_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        mapped.append({
            "id": str(appt_id),
            "customer_name": customer_name or None,
            "customer_email": customer_email or None,
            "service_name": service or None,
            "starts_at": date_parsed,
            "status": status or None,
            "raw": norm_row
        })
    
    return mapped


def map_payments_to_db(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map payment CSV rows to database format"""
    mapped = []
    for row in rows:
        norm_row = {normalize_key(k): v for k, v in row.items()}
        
        customer_name = norm_row.get("customer", "") or norm_row.get("customer_name", "")
        service = norm_row.get("service", "") or norm_row.get("service_name", "")
        date_raw = norm_row.get("date", "") or norm_row.get("payment_date", "")
        amount = norm_row.get("price", "") or norm_row.get("amount", "")
        status = norm_row.get("payment_status", "") or norm_row.get("status", "")
        
        date_parsed = parse_date_flexible(date_raw) if date_raw else None
        
        payment_id = norm_row.get("id") or norm_row.get("payment_id")
        if not payment_id:
            raw = f"{customer_name}|{date_raw}|{amount}"
            payment_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        mapped.append({
            "id": str(payment_id),
            "customer_name": customer_name or None,
            "service_name": service or None,
            "date": date_parsed,
            "amount": float(amount) if amount and amount.replace(".", "").isdigit() else None,
            "status": status or None,
            "raw": norm_row
        })
    
    return mapped


def load_csv_to_database(csv_files: Dict[str, Path]):
    """Load CSV data to PostgreSQL and return mapped data"""
    print("\n" + "="*60)
    print("📤 CARGANDO DATOS A POSTGRESQL")
    print("="*60)
    
    pool = get_pool()
    
    # Mappers
    mappers = {
        "customers": map_customers_to_db,
        "appointments": map_appointments_to_db,
        "payments": map_payments_to_db
    }
    
    # Tables
    tables = {
        "customers": "booknetic_customers",
        "appointments": "booknetic_appointments",
        "payments": "booknetic_payments"
    }
    
    results = {
        "customers": [],
        "appointments": [],
        "payments": []
    }
    
    for module_name, csv_path in csv_files.items():
        if not csv_path or not csv_path.exists():
            print(f"⚠️ CSV no encontrado para {module_name}")
            continue
        
        print(f"\n📁 Procesando {csv_path.name}...")
        
        try:
            # Parse CSV
            rows = parse_csv_file(csv_path)
            print(f"   📊 {len(rows)} filas leídas del CSV")
            
            # Map to DB format
            mapper = mappers.get(module_name)
            if not mapper:
                print(f"   ⚠️ No hay mapper para {module_name}")
                continue
            
            mapped = mapper(rows)
            print(f"   🔄 {len(mapped)} filas mapeadas")
            
            # Store mapped data
            results[module_name] = mapped
            
            # Upsert to DB
            table = tables.get(module_name)
            if not table:
                print(f"   ⚠️ No hay tabla para {module_name}")
                continue
            
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Prepare upsert
                    for item in mapped:
                        keys = list(item.keys())
                        placeholders = ", ".join([f"%({k})s" for k in keys])
                        updates = ", ".join([f"{k} = EXCLUDED.{k}" for k in keys if k != "id"])
                        
                        sql = f"""
                        INSERT INTO {table} ({", ".join(keys)})
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO UPDATE SET {updates}
                        """
                        cur.execute(sql, item)
                    
                    conn.commit()
                    print(f"   ✅ {len(mapped)} registros insertados/actualizados en {table}")
        
        except Exception as e:
            print(f"   ❌ Error procesando {module_name}: {e}")
            import traceback
            traceback.print_exc()
    
    return results


def fetch() -> Dict[str, Any]:
    """
    Función principal que exporta y carga datos de Booknetic
    Retorna un diccionario con appointments, customers, payments
    """
    print("\n" + "="*60)
    print("🚀 BOOKNETIC EXPORT CON REQUESTS")
    print("="*60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Crear directorio de descargas
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    
    # Verificar credenciales
    if not USERNAME or not PASSWORD:
        raise RuntimeError("BOOKNETIC_USERNAME y BOOKNETIC_PASSWORD deben estar configurados")
    
    print(f"🌐 URL: {BASE_URL}")
    print(f"👤 Usuario: {USERNAME}")
    
    # Login
    session = create_session_and_login()
    if not session:
        raise RuntimeError("Login falló")
    
    # Download CSVs
    csv_files = {}
    modules = [
        ("customers", "Customers"),
        ("appointments", "Appointments"),
        ("payments", "Payments")
    ]
    
    for module_name, display_name in modules:
        csv_path = download_csv(session, module_name, display_name)
        if csv_path:
            csv_files[module_name] = csv_path
    
    print(f"\n📊 CSVs descargados: {len(csv_files)}/{len(modules)}")
    
    # Parse CSVs and map to DB format (but don't insert yet)
    print("\n📋 Parseando y mapeando datos...")
    
    results = {
        "customers": [],
        "appointments": [],
        "payments": []
    }
    
    mappers = {
        "customers": map_customers_to_db,
        "appointments": map_appointments_to_db,
        "payments": map_payments_to_db
    }
    
    for module_name, csv_path in csv_files.items():
        if not csv_path or not csv_path.exists():
            continue
        
        try:
            rows = parse_csv_file(csv_path)
            mapper = mappers.get(module_name)
            if mapper:
                mapped = mapper(rows)
                results[module_name] = mapped
                print(f"   ✅ {module_name.capitalize()}: {len(mapped)} registros mapeados")
        except Exception as e:
            print(f"   ❌ Error mapeando {module_name}: {e}")
    
    print("\n" + "="*60)
    print("📊 RESUMEN")
    print("="*60)
    print(f"💾 Customers: {len(results.get('customers', []))} registros")
    print(f"💾 Appointments: {len(results.get('appointments', []))} registros")
    print(f"💾 Payments: {len(results.get('payments', []))} registros")
    print("="*60)
    print("✅ Datos descargados y mapeados (job_scrape_booknetic hará el upsert)")
    print("="*60)
    
    return results


if __name__ == "__main__":
    fetch()

