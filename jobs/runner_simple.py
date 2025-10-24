"""
Runner simple SIN APScheduler - usa loop + sleep
Compatible con Railway y más confiable
"""
import os
import time
import datetime as dt
from dotenv import load_dotenv

from db.utils import run_with_job_meta, print_db_identity
from db.migrate import ensure_schema
from jobs.job_scrape_booknetic import run as run_booknetic

# Importar sheets solo si está configurado
try:
    from jobs.job_import_sheets import run as run_sheets
    SHEETS_ENABLED = True
except Exception:
    SHEETS_ENABLED = False
    print("[runner] Google Sheets import disabled (missing config)")


def load_env() -> None:
    """Load environment variables"""
    load_dotenv()


def run_job_safely(job_name: str, job_func):
    """Ejecuta un job con manejo de errores"""
    try:
        print(f"\n{'='*60}")
        print(f"🚀 Ejecutando job: {job_name}")
        print(f"⏰ Hora: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        run_with_job_meta(job_name, job_func)
        
        print(f"\n✅ Job '{job_name}' completado exitosamente\n")
    except Exception as e:
        print(f"\n❌ Error en job '{job_name}': {e}\n")
        import traceback
        traceback.print_exc()


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
    BOOKNETIC_INTERVAL = int(os.getenv("BOOKNETIC_INTERVAL", "900"))  # 15 min por defecto
    SHEETS_INTERVAL = int(os.getenv("SHEETS_INTERVAL", "600"))  # 10 min por defecto
    
    print(f"⚙️ Configuración:")
    print(f"   - Booknetic: cada {BOOKNETIC_INTERVAL//60} minutos")
    if SHEETS_ENABLED:
        print(f"   - Sheets: cada {SHEETS_INTERVAL//60} minutos")
    else:
        print(f"   - Sheets: DESHABILITADO")
    print()
    
    # Ejecutar Booknetic inmediatamente al inicio
    print("🔷 Ejecución inicial de Booknetic...")
    run_job_safely("booknetic_scrape", run_booknetic)
    
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
                run_job_safely("booknetic_scrape", run_booknetic)
                last_booknetic_run = current_time
            
            # Ejecutar Sheets si está habilitado y pasó el intervalo
            if SHEETS_ENABLED and current_time - last_sheets_run >= SHEETS_INTERVAL:
                run_job_safely("sheets_import", run_sheets)
                last_sheets_run = current_time
            
            # Calcular tiempo hasta próxima ejecución
            time_to_next_booknetic = BOOKNETIC_INTERVAL - (current_time - last_booknetic_run)
            next_run = dt.datetime.now() + dt.timedelta(seconds=time_to_next_booknetic)
            
            print(f"💤 Esperando... Próxima ejecución de Booknetic: {next_run.strftime('%H:%M:%S')}")
            
            # Dormir por 60 segundos (1 minuto)
            time.sleep(60)
            
    except (KeyboardInterrupt, SystemExit):
        print("\n" + "="*60)
        print("🛑 Runner detenido")
        print("="*60)
        time.sleep(0.5)


if __name__ == "__main__":
    main()

