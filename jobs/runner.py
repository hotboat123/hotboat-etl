"""
Runner simple SIN APScheduler - usa loop + sleep
Compatible con Railway y más confiable

Jobs: Meta Ads, Flujo Caja (según env).
Sheets / Informacion Reserva / Stock / Precios Extras / export Reservas_Con_Extras_Sheets no se ejecutan aquí;
para import manual: python -m jobs.job_import_sheets. Booknetic: BOOKNETIC_SYNC_ENABLED=1 y python -m jobs.job_scrape_booknetic.
"""
import os
import sys
import time
import base64
import io
import datetime as dt
import threading

# Agregar la raíz del proyecto al path para que funcione desde cualquier directorio
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from db.utils import run_with_job_meta, print_db_identity
from db.migrate import ensure_schema

# Importar dotenv solo si está disponible (para desarrollo local)
try:
    from dotenv import load_dotenv, dotenv_values
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("[env] python-dotenv not available - using system env vars only (OK for Railway)")

try:
    from jobs.job_meta_ads import run as run_meta_ads
except Exception as e:
    run_meta_ads = None  # type: ignore[assignment]
    print(f"[runner] Meta Ads module not available: {e}")

try:
    from jobs.job_flujo_caja import run as run_flujo_caja
    FLUJO_CAJA_ENABLED = bool(os.getenv("LOOKER_SPREADSHEET_ID"))
except Exception as e:
    run_flujo_caja = None  # type: ignore[assignment]
    FLUJO_CAJA_ENABLED = False
    print(f"[runner] Flujo Caja module not available: {e}")


def load_env() -> None:
    """Load environment variables"""
    if DOTENV_AVAILABLE:
        load_dotenv()
        print("[env] Loaded .env file")

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
        print(f"Ejecutando job: {job_name}")
        print(f"Hora: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        run_with_job_meta(job_name, job_func)

        print(f"\n[OK] Job '{job_name}' completado exitosamente\n")
        return True
    except Exception as e:
        print(f"\n[ERROR] Job '{job_name}': {e}\n")
        import traceback
        traceback.print_exc()

        try:
            from utils.notifications import notify_job_failure
            notify_job_failure(job_name, e)
        except Exception:
            pass

        return False


def _start_dashboard() -> None:
    """Arranca el dashboard FastAPI en un hilo daemon."""
    try:
        import uvicorn
        from app.main import app
        port = int(os.getenv("PORT", "8080"))
        print(f"[dashboard] Iniciando en http://0.0.0.0:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    except Exception as e:
        print(f"[dashboard] No se pudo iniciar: {e}")


def main() -> None:
    """Main loop - ejecuta jobs cada X minutos"""
    load_env()

    # Iniciar dashboard en hilo de fondo
    t = threading.Thread(target=_start_dashboard, daemon=True)
    t.start()

    meta_ads_enabled = bool(
        os.getenv("META_ACCESS_TOKEN") and os.getenv("META_AD_ACCOUNT_ID")
    ) and (run_meta_ads is not None)

    print("="*60)
    print("HotBoat ETL - Runner")
    print("="*60)
    print()

    print_db_identity()
    ensure_schema()

    META_ADS_INTERVAL = int(os.getenv("META_ADS_INTERVAL", "3600"))         # 1 h
    FLUJO_CAJA_INTERVAL = int(os.getenv("FLUJO_CAJA_INTERVAL", "1800"))     # 30 min

    print("Configuracion:")
    if meta_ads_enabled:
        print(f"   - Meta Ads: cada {META_ADS_INTERVAL//60} minutos")
    else:
        print("   - Meta Ads: DESHABILITADO (falta META_ACCESS_TOKEN / META_AD_ACCOUNT_ID o modulo)")
    if FLUJO_CAJA_ENABLED:
        print(f"   - Flujo Caja: cada {FLUJO_CAJA_INTERVAL//60} minutos")
    else:
        print("   - Flujo Caja: DESHABILITADO (falta LOOKER_SPREADSHEET_ID)")
    print()

    failure_tracker = {
        "meta_ads_sync": {"consecutive_failures": 0},
        "flujo_caja_sync": {"consecutive_failures": 0},
    }

    # --- Ejecución inicial ---
    if meta_ads_enabled and run_meta_ads is not None:
        print("Ejecucion inicial de Meta Ads...")
        success = run_job_safely("meta_ads_sync", run_meta_ads)
        if not success:
            failure_tracker["meta_ads_sync"]["consecutive_failures"] += 1

    if FLUJO_CAJA_ENABLED and run_flujo_caja is not None:
        print("Ejecucion inicial de Flujo Caja...")
        success = run_job_safely("flujo_caja_sync", run_flujo_caja)
        if not success:
            failure_tracker["flujo_caja_sync"]["consecutive_failures"] += 1

    last_meta_ads_run = time.time()
    last_flujo_caja_run = time.time()

    print("\n" + "="*60)
    print("Loop iniciado - Esperando proximas ejecuciones...")
    print("="*60)
    print()

    try:
        while True:
            current_time = time.time()

            # Meta Ads
            if (
                meta_ads_enabled
                and run_meta_ads is not None
                and current_time - last_meta_ads_run >= META_ADS_INTERVAL
            ):
                success = run_job_safely("meta_ads_sync", run_meta_ads)
                last_meta_ads_run = current_time
                if success:
                    if failure_tracker["meta_ads_sync"]["consecutive_failures"] >= 3:
                        try:
                            from utils.notifications import notify_success_after_failure
                            notify_success_after_failure(
                                "meta_ads_sync",
                                failure_tracker["meta_ads_sync"]["consecutive_failures"],
                            )
                        except Exception:
                            pass
                    failure_tracker["meta_ads_sync"]["consecutive_failures"] = 0
                else:
                    failure_tracker["meta_ads_sync"]["consecutive_failures"] += 1

            # Flujo Caja
            if FLUJO_CAJA_ENABLED and run_flujo_caja is not None and current_time - last_flujo_caja_run >= FLUJO_CAJA_INTERVAL:
                success = run_job_safely("flujo_caja_sync", run_flujo_caja)
                last_flujo_caja_run = current_time
                if success:
                    if failure_tracker["flujo_caja_sync"]["consecutive_failures"] >= 3:
                        try:
                            from utils.notifications import notify_success_after_failure
                            notify_success_after_failure("flujo_caja_sync",
                                failure_tracker["flujo_caja_sync"]["consecutive_failures"])
                        except Exception:
                            pass
                    failure_tracker["flujo_caja_sync"]["consecutive_failures"] = 0
                else:
                    failure_tracker["flujo_caja_sync"]["consecutive_failures"] += 1

            hints: list[str] = []
            if meta_ads_enabled and run_meta_ads is not None:
                sec = META_ADS_INTERVAL - (current_time - last_meta_ads_run)
                hints.append(
                    f"Meta Ads en ~{max(0, int(sec // 60))}m ({(dt.datetime.now() + dt.timedelta(seconds=max(sec, 0))).strftime('%H:%M')})"
                )
            if FLUJO_CAJA_ENABLED and run_flujo_caja is not None:
                sec = FLUJO_CAJA_INTERVAL - (current_time - last_flujo_caja_run)
                hints.append(
                    f"Flujo Caja en ~{max(0, int(sec // 60))}m"
                )
            if hints:
                print("Esperando... " + " | ".join(hints))
            else:
                print("Esperando... (sin jobs programados en loop, poll 60s)")

            time.sleep(60)

    except (KeyboardInterrupt, SystemExit):
        print("\n" + "="*60)
        print("Runner detenido")
        print("="*60)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
