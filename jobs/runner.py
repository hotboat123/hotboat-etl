"""
Runner simple SIN APScheduler - usa loop + sleep
Compatible con Railway y más confiable
"""
import os
import sys
import time
import base64
import io
import datetime as dt

# Agregar la raíz del proyecto al path para que funcione desde cualquier directorio
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from db.utils import run_with_job_meta, print_db_identity
from db.migrate import ensure_schema
from jobs.job_scrape_booknetic import run as run_booknetic

# Importar dotenv solo si está disponible (para desarrollo local)
try:
    from dotenv import load_dotenv, dotenv_values
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("[env] python-dotenv not available - using system env vars only (OK for Railway)")

# Importar sheets solo si está configurado
try:
    from jobs.job_import_sheets import run as run_sheets
    SHEETS_ENABLED = True
except Exception:
    SHEETS_ENABLED = False
    print("[runner] Google Sheets import disabled (missing config)")


def load_env() -> None:
    """Load environment variables"""
    if DOTENV_AVAILABLE:
        # Load .env if present in container (useful locally)
        load_dotenv()
        print("[env] Loaded .env file")
        
        # Optionally load a base64-encoded .env provided via env var (Railway-safe)
        b64 = os.getenv("DOTENV_BASE64")
        if b64:
            try:
                content = base64.b64decode(b64).decode("utf-8")
                for k, v in (dotenv_values(stream=io.StringIO(content)) or {}).items():
                    if v is not None and k not in os.environ:
                        os.environ[k] = v
                print("[env] Loaded DOTENV_BASE64")
            except Exception as e:  # noqa: BLE001
                print(f"[env] Failed to load DOTENV_BASE64: {e}")
    else:
        print("[env] Using system environment variables (Railway mode)")


def run_job_safely(job_name: str, job_func):
    """Ejecuta un job con manejo de errores"""
    try:
        print(f"\n{'='*60}")
        print(f"🚀 Ejecutando job: {job_name}")
        print(f"⏰ Hora: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        run_with_job_meta(job_name, job_func)
        
        print(f"\n✅ Job '{job_name}' completado exitosamente\n")
        return True
    except Exception as e:
        print(f"\n❌ Error en job '{job_name}': {e}\n")
        import traceback
        traceback.print_exc()
        
        # Enviar notificación de error
        try:
            from utils.notifications import notify_job_failure
            notify_job_failure(job_name, e)
        except Exception:
            pass  # Si falla la notificación, no romper el flujo
        
        return False


def main() -> None:
    """Main loop - ejecuta jobs cada X minutos"""
    load_env()
    
    print("="*60)
    print("🚀 HotBoat ETL - Runner Simple (SIN APScheduler)")
    print("="*60)
    print()
    
    # Ensure DB schema exists
    print_db_identity()
    ensure_schema()
    
    # Configuración de intervalos (en segundos)
    BOOKNETIC_INTERVAL = int(os.getenv("BOOKNETIC_INTERVAL", "1800"))  # 30 min por defecto
    SHEETS_INTERVAL = int(os.getenv("SHEETS_INTERVAL", "600"))  # 10 min por defecto
    
    print(f"⚙️ Configuración:")
    print(f"   - Booknetic: cada {BOOKNETIC_INTERVAL//60} minutos")
    if SHEETS_ENABLED:
        print(f"   - Sheets: cada {SHEETS_INTERVAL//60} minutos")
    else:
        print(f"   - Sheets: DESHABILITADO")
    print()
    
    # Rastrear fallos consecutivos para notificaciones inteligentes
    failure_tracker = {
        "booknetic_scrape": {"consecutive_failures": 0, "last_notified": 0},
        "sheets_import": {"consecutive_failures": 0, "last_notified": 0}
    }
    
    # Ejecutar Booknetic inmediatamente al inicio
    print("🔷 Ejecución inicial de Booknetic...")
    success = run_job_safely("booknetic_scrape", run_booknetic)
    if not success:
        failure_tracker["booknetic_scrape"]["consecutive_failures"] += 1
    
    last_booknetic_run = time.time()
    last_sheets_run = time.time()
    
    print("\n" + "="*60)
    print("⏰ Loop iniciado - Esperando próximas ejecuciones...")
    print("="*60)
    print()
    
    try:
        while True:
            current_time = time.time()
            
            # Ejecutar Booknetic si pasó el intervalo
            if current_time - last_booknetic_run >= BOOKNETIC_INTERVAL:
                success = run_job_safely("booknetic_scrape", run_booknetic)
                last_booknetic_run = current_time
                
                # Tracking de fallos
                if success:
                    # Si se recuperó después de fallos, notificar
                    if failure_tracker["booknetic_scrape"]["consecutive_failures"] >= 3:
                        try:
                            from utils.notifications import notify_success_after_failure
                            notify_success_after_failure("booknetic_scrape", 
                                failure_tracker["booknetic_scrape"]["consecutive_failures"])
                        except Exception:
                            pass
                    failure_tracker["booknetic_scrape"]["consecutive_failures"] = 0
                else:
                    failure_tracker["booknetic_scrape"]["consecutive_failures"] += 1
            
            # Ejecutar Sheets si está habilitado y pasó el intervalo
            if SHEETS_ENABLED and current_time - last_sheets_run >= SHEETS_INTERVAL:
                success = run_job_safely("sheets_import", run_sheets)
                last_sheets_run = current_time
                
                # Tracking de fallos
                if success:
                    # Si se recuperó después de fallos, notificar
                    if failure_tracker["sheets_import"]["consecutive_failures"] >= 3:
                        try:
                            from utils.notifications import notify_success_after_failure
                            notify_success_after_failure("sheets_import",
                                failure_tracker["sheets_import"]["consecutive_failures"])
                        except Exception:
                            pass
                    failure_tracker["sheets_import"]["consecutive_failures"] = 0
                else:
                    failure_tracker["sheets_import"]["consecutive_failures"] += 1
            
            # Calcular tiempo hasta próxima ejecución
            time_to_next_booknetic = BOOKNETIC_INTERVAL - (current_time - last_booknetic_run)
            next_run = dt.datetime.now() + dt.timedelta(seconds=time_to_next_booknetic)
            
            # Mostrar estado de salud
            health_status = "✅" if failure_tracker["booknetic_scrape"]["consecutive_failures"] == 0 else f"⚠️({failure_tracker['booknetic_scrape']['consecutive_failures']} fallos)"
            print(f"💤 Esperando... Próxima ejecución de Booknetic: {next_run.strftime('%H:%M:%S')} {health_status}")
            
            # Dormir por 60 segundos (1 minuto)
            time.sleep(60)
            
    except (KeyboardInterrupt, SystemExit):
        print("\n" + "="*60)
        print("🛑 Runner detenido")
        print("="*60)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
