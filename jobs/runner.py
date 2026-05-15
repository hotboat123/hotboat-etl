"""
Runner simple SIN APScheduler - usa loop + sleep
Compatible con Railway y más confiable

Jobs: Sheets, export reservas, Meta Ads, Flujo Caja (según env).
Booknetic no se ejecuta aquí; para scrape manual: BOOKNETIC_SYNC_ENABLED=1 y python -m jobs.job_scrape_booknetic.
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

# Importar sheets solo si está configurado
try:
    from jobs.job_import_sheets import run as run_sheets
    SHEETS_ENABLED = True
except Exception:
    SHEETS_ENABLED = False
    print("[runner] Google Sheets import disabled (missing config)")

# Importar export de reservas a sheets
try:
    from jobs.export_reservas_to_sheets import run as run_export_reservas
    EXPORT_RESERVAS_ENABLED = True
except Exception as e:
    EXPORT_RESERVAS_ENABLED = False
    print(f"[runner] Export Reservas to Sheets disabled: {e}")

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

try:
    from jobs.job_collect_lodging import run as run_collect_lodging
    LODGING_ENABLED = True
except Exception as e:
    run_collect_lodging = None  # type: ignore[assignment]
    LODGING_ENABLED = False
    print(f"[runner] Lodging module not available: {e}")

try:
    from jobs.job_collect_weather import run as run_collect_weather
    WEATHER_ENABLED = bool(os.getenv("OPENWEATHER_API_KEY"))
except Exception as e:
    run_collect_weather = None  # type: ignore[assignment]
    WEATHER_ENABLED = False
    print(f"[runner] Weather module not available: {e}")

try:
    from jobs.job_collect_traffic import run as run_collect_traffic
    TRAFFIC_ENABLED = os.getenv("TRAFFIC_SCRAPING_ENABLED", "1") not in ("0", "false", "no")
except Exception as e:
    run_collect_traffic = None  # type: ignore[assignment]
    TRAFFIC_ENABLED = False
    print(f"[runner] Traffic module not available: {e}")

try:
    from jobs.job_pucon_flow_index import run as run_pucon_flow_index
    FLOW_INDEX_ENABLED = True
except Exception as e:
    run_pucon_flow_index = None  # type: ignore[assignment]
    FLOW_INDEX_ENABLED = False
    print(f"[runner] Pucon Flow Index module not available: {e}")


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

    SHEETS_INTERVAL         = int(os.getenv("SHEETS_INTERVAL", "600"))           # 10 min
    EXPORT_RESERVAS_INTERVAL = int(os.getenv("EXPORT_RESERVAS_INTERVAL", "900")) # 15 min
    META_ADS_INTERVAL       = int(os.getenv("META_ADS_INTERVAL", "3600"))        # 1 h
    FLUJO_CAJA_INTERVAL     = int(os.getenv("FLUJO_CAJA_INTERVAL", "1800"))      # 30 min
    GOOGLE_ADS_INTERVAL     = int(os.getenv("GOOGLE_ADS_INTERVAL", "3600"))       # 1 h
    LODGING_INTERVAL        = int(os.getenv("LODGING_INTERVAL", "21600"))        # 6 h
    WEATHER_INTERVAL        = int(os.getenv("WEATHER_INTERVAL", "3600"))         # 1 h
    TRAFFIC_INTERVAL        = int(os.getenv("TRAFFIC_INTERVAL", "10800"))        # 3 h
    FLOW_INDEX_INTERVAL     = int(os.getenv("FLOW_INDEX_INTERVAL", "3600"))      # 1 h

    print("Configuracion:")
    if SHEETS_ENABLED:
        print(f"   - Sheets: cada {SHEETS_INTERVAL//60} minutos")
    else:
        print("   - Sheets: DESHABILITADO")
    if EXPORT_RESERVAS_ENABLED:
        print(f"   - Export Reservas: cada {EXPORT_RESERVAS_INTERVAL//60} minutos")
    else:
        print("   - Export Reservas: DESHABILITADO")
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
    if LODGING_ENABLED:
        print(f"   - Alojamiento Booking: cada {LODGING_INTERVAL//3600} horas")
    else:
        print("   - Alojamiento Booking: DESHABILITADO")
    if WEATHER_ENABLED:
        print(f"   - Clima Pucón: cada {WEATHER_INTERVAL//60} minutos")
    else:
        print("   - Clima Pucón: DESHABILITADO (falta OPENWEATHER_API_KEY)")
    if TRAFFIC_ENABLED:
        print(f"   - Tráfico Pucón (Google Maps scraping): cada {TRAFFIC_INTERVAL//60} minutos")
    else:
        print("   - Tráfico Pucón: DESHABILITADO (TRAFFIC_SCRAPING_ENABLED=0)")
    if FLOW_INDEX_ENABLED:
        print(f"   - Flujo Turístico Index: cada {FLOW_INDEX_INTERVAL//60} minutos")
    print()

    failure_tracker = {
        "sheets_import": {"consecutive_failures": 0},
        "export_reservas_sheets": {"consecutive_failures": 0},
        "meta_ads_sync": {"consecutive_failures": 0},
        "flujo_caja_sync": {"consecutive_failures": 0},
        "google_ads_sync": {"consecutive_failures": 0},
        "collect_lodging": {"consecutive_failures": 0},
        "collect_weather": {"consecutive_failures": 0},
        "collect_traffic": {"consecutive_failures": 0},
        "pucon_flow_index": {"consecutive_failures": 0},
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

    if GOOGLE_ADS_ENABLED and run_google_ads is not None:
        print("Ejecucion inicial de Google Ads...")
        success = run_job_safely("google_ads_sync", run_google_ads)
        if not success:
            failure_tracker["google_ads_sync"]["consecutive_failures"] += 1

    if LODGING_ENABLED and run_collect_lodging is not None:
        print("Ejecucion inicial de Alojamiento Booking...")
        success = run_job_safely("collect_lodging", run_collect_lodging)
        if not success:
            failure_tracker["collect_lodging"]["consecutive_failures"] += 1

    if WEATHER_ENABLED and run_collect_weather is not None:
        print("Ejecucion inicial de Clima Pucón...")
        success = run_job_safely("collect_weather", run_collect_weather)
        if not success:
            failure_tracker["collect_weather"]["consecutive_failures"] += 1

    if TRAFFIC_ENABLED and run_collect_traffic is not None:
        print("Ejecucion inicial de Tráfico Pucón...")
        success = run_job_safely("collect_traffic", run_collect_traffic)
        if not success:
            failure_tracker["collect_traffic"]["consecutive_failures"] += 1

    if FLOW_INDEX_ENABLED and run_pucon_flow_index is not None:
        print("Ejecucion inicial de Flujo Turístico Index...")
        success = run_job_safely("pucon_flow_index", run_pucon_flow_index)
        if not success:
            failure_tracker["pucon_flow_index"]["consecutive_failures"] += 1

    last_sheets_run = time.time()
    last_export_reservas_run = time.time()
    last_meta_ads_run = time.time()
    last_flujo_caja_run = time.time()
    last_google_ads_run = time.time()
    last_lodging_run = time.time()
    last_weather_run = time.time()
    last_traffic_run = time.time()
    last_flow_index_run = time.time()

    print("\n" + "="*60)
    print("Loop iniciado - Esperando proximas ejecuciones...")
    print("="*60)
    print()

    try:
        while True:
            current_time = time.time()

            # Sheets
            if SHEETS_ENABLED and current_time - last_sheets_run >= SHEETS_INTERVAL:
                success = run_job_safely("sheets_import", run_sheets)
                last_sheets_run = current_time
                if success:
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

            # Export Reservas
            if EXPORT_RESERVAS_ENABLED and current_time - last_export_reservas_run >= EXPORT_RESERVAS_INTERVAL:
                try:
                    success = run_job_safely("export_reservas_sheets", run_export_reservas)
                    last_export_reservas_run = current_time
                    if success:
                        if failure_tracker["export_reservas_sheets"]["consecutive_failures"] >= 3:
                            try:
                                from utils.notifications import notify_success_after_failure
                                notify_success_after_failure("export_reservas_sheets",
                                    failure_tracker["export_reservas_sheets"]["consecutive_failures"])
                            except Exception:
                                pass
                        failure_tracker["export_reservas_sheets"]["consecutive_failures"] = 0
                    else:
                        failure_tracker["export_reservas_sheets"]["consecutive_failures"] += 1
                except Exception as e:
                    print(f"[runner] Error ejecutando export_reservas_sheets: {e}")
                    failure_tracker["export_reservas_sheets"]["consecutive_failures"] += 1
                    last_export_reservas_run = current_time

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

            # Google Ads
            if GOOGLE_ADS_ENABLED and run_google_ads is not None and current_time - last_google_ads_run >= GOOGLE_ADS_INTERVAL:
                success = run_job_safely("google_ads_sync", run_google_ads)
                last_google_ads_run = current_time
                if success:
                    failure_tracker["google_ads_sync"]["consecutive_failures"] = 0
                else:
                    failure_tracker["google_ads_sync"]["consecutive_failures"] += 1

            # Alojamiento Booking
            if LODGING_ENABLED and run_collect_lodging is not None and current_time - last_lodging_run >= LODGING_INTERVAL:
                success = run_job_safely("collect_lodging", run_collect_lodging)
                last_lodging_run = current_time
                if success:
                    failure_tracker["collect_lodging"]["consecutive_failures"] = 0
                else:
                    failure_tracker["collect_lodging"]["consecutive_failures"] += 1

            # Clima Pucón
            if WEATHER_ENABLED and run_collect_weather is not None and current_time - last_weather_run >= WEATHER_INTERVAL:
                success = run_job_safely("collect_weather", run_collect_weather)
                last_weather_run = current_time
                if success:
                    failure_tracker["collect_weather"]["consecutive_failures"] = 0
                else:
                    failure_tracker["collect_weather"]["consecutive_failures"] += 1

            # Tráfico Pucón
            if TRAFFIC_ENABLED and run_collect_traffic is not None and current_time - last_traffic_run >= TRAFFIC_INTERVAL:
                success = run_job_safely("collect_traffic", run_collect_traffic)
                last_traffic_run = current_time
                if success:
                    failure_tracker["collect_traffic"]["consecutive_failures"] = 0
                else:
                    failure_tracker["collect_traffic"]["consecutive_failures"] += 1

            # Índice de flujo turístico
            if FLOW_INDEX_ENABLED and run_pucon_flow_index is not None and current_time - last_flow_index_run >= FLOW_INDEX_INTERVAL:
                success = run_job_safely("pucon_flow_index", run_pucon_flow_index)
                last_flow_index_run = current_time
                if success:
                    failure_tracker["pucon_flow_index"]["consecutive_failures"] = 0
                else:
                    failure_tracker["pucon_flow_index"]["consecutive_failures"] += 1

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
