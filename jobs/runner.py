"""
Runner simple SIN APScheduler - usa loop + sleep
Compatible con Railway y más confiable

Jobs: Meta Ads, Flujo Caja, Google Ads (según env).
"""
import os
import sys
import time
import base64
import io
import logging
import datetime as dt

# stdout/stderr en Docker/Railway quedan con buffer completo (no de linea), asi que
# los print() pueden tardar minutos en aparecer en los logs. Forzamos line-buffering.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# Sin esto, cualquier logging.getLogger(__name__).info(...) (ej. job_google_ads)
# no imprime nada: no hay handler configurado en el logger root.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

# Agregar la raíz del proyecto al path para que funcione desde cualquier directorio
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from db.utils import print_db_identity
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

try:
    from jobs.job_google_ads import run as run_google_ads
    GOOGLE_ADS_ENABLED = bool(
        os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN") and os.getenv("GOOGLE_ADS_CUSTOMER_ID")
    )
except Exception as e:
    run_google_ads = None  # type: ignore[assignment]
    GOOGLE_ADS_ENABLED = False
    print(f"[runner] Google Ads module not available: {e}")


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


def run_job_safely(job_name: str, job_func) -> bool:
    """Ejecuta un job con manejo de errores"""
    try:
        print(f"\n{'='*60}")
        print(f"Ejecutando job: {job_name}")
        print(f"Hora: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        result = job_func()

        if isinstance(result, int):
            print(f"\n[OK] Job '{job_name}' completado — {result} filas procesadas\n")
        else:
            print(f"\n[OK] Job '{job_name}' completado exitosamente\n")
        return True
    except Exception as e:
        print(f"\n[ERROR] Job '{job_name}': {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main() -> None:
    """Main loop - ejecuta jobs cada X minutos"""
    load_env()

    meta_ads_enabled = bool(
        os.getenv("META_ACCESS_TOKEN") and os.getenv("META_AD_ACCOUNT_ID")
    ) and (run_meta_ads is not None)

    print("="*60)
    print("HotBoat ETL - Runner")
    print("="*60)
    print()

    ensure_schema()

    META_ADS_INTERVAL       = int(os.getenv("META_ADS_INTERVAL", "3600"))        # 1 h
    FLUJO_CAJA_INTERVAL     = int(os.getenv("FLUJO_CAJA_INTERVAL", "1800"))      # 30 min
    GOOGLE_ADS_INTERVAL     = int(os.getenv("GOOGLE_ADS_INTERVAL", "3600"))       # 1 h

    print("Configuracion:")
    if meta_ads_enabled:
        print(f"   - Meta Ads: cada {META_ADS_INTERVAL//60} minutos")
    else:
        print("   - Meta Ads: DESHABILITADO (falta META_ACCESS_TOKEN / META_AD_ACCOUNT_ID o modulo)")
    if FLUJO_CAJA_ENABLED:
        print(f"   - Flujo Caja: cada {FLUJO_CAJA_INTERVAL//60} minutos")
    else:
        print("   - Flujo Caja: DESHABILITADO (falta LOOKER_SPREADSHEET_ID)")
    if GOOGLE_ADS_ENABLED:
        print(f"   - Google Ads: cada {GOOGLE_ADS_INTERVAL//60} minutos")
    else:
        print("   - Google Ads: DESHABILITADO (falta GOOGLE_ADS_DEVELOPER_TOKEN / GOOGLE_ADS_CUSTOMER_ID)")
    print()

    # --- Ejecución inicial ---
    if meta_ads_enabled and run_meta_ads is not None:
        print("Ejecucion inicial de Meta Ads...")
        run_job_safely("meta_ads_sync", run_meta_ads)

    if FLUJO_CAJA_ENABLED and run_flujo_caja is not None:
        print("Ejecucion inicial de Flujo Caja...")
        run_job_safely("flujo_caja_sync", run_flujo_caja)

    if GOOGLE_ADS_ENABLED and run_google_ads is not None:
        print("Ejecucion inicial de Google Ads...")
        run_job_safely("google_ads_sync", run_google_ads)

    last_meta_ads_run = time.time()
    last_flujo_caja_run = time.time()
    last_google_ads_run = time.time()

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
                run_job_safely("meta_ads_sync", run_meta_ads)
                last_meta_ads_run = current_time

            # Flujo Caja
            if FLUJO_CAJA_ENABLED and run_flujo_caja is not None and current_time - last_flujo_caja_run >= FLUJO_CAJA_INTERVAL:
                run_job_safely("flujo_caja_sync", run_flujo_caja)
                last_flujo_caja_run = current_time

            # Google Ads
            if GOOGLE_ADS_ENABLED and run_google_ads is not None and current_time - last_google_ads_run >= GOOGLE_ADS_INTERVAL:
                run_job_safely("google_ads_sync", run_google_ads)
                last_google_ads_run = current_time

            time_to_next = META_ADS_INTERVAL - (current_time - last_meta_ads_run)
            next_run = dt.datetime.now() + dt.timedelta(seconds=max(time_to_next, 0))
            print(f"Esperando... Proxima ejecucion Meta Ads: {next_run.strftime('%H:%M:%S')}")

            time.sleep(60)

    except (KeyboardInterrupt, SystemExit):
        print("\n" + "="*60)
        print("Runner detenido")
        print("="*60)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
