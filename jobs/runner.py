import os
import time
import base64
import io
import datetime as dt
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv, dotenv_values

from db.utils import run_with_job_meta, print_db_identity
from db.migrate import ensure_schema
from jobs.job_import_sheets import run as run_sheets
from jobs.job_scrape_booknetic import run as run_booknetic


def load_env() -> None:
    # Load .env if present in container (useful locally)
    load_dotenv()
    # Optionally load a base64-encoded .env provided via env var (Railway-safe)
    b64 = os.getenv("DOTENV_BASE64")
    if b64:
        try:
            content = base64.b64decode(b64).decode("utf-8")
            for k, v in (dotenv_values(stream=io.StringIO(content)) or {}).items():
                if v is not None and k not in os.environ:
                    os.environ[k] = v
        except Exception as e:  # noqa: BLE001
            print(f"[env] Failed to load DOTENV_BASE64: {e}")


def main() -> None:
    load_env()

    # Ensure DB schema exists before scheduling jobs
    print_db_identity()
    ensure_schema()

    scheduler = BlockingScheduler(
        timezone=os.getenv("TZ", "UTC"),
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 600,
        },
    )

    # One-time boot run for Booknetic
    scheduler.add_job(
        lambda: run_with_job_meta("booknetic_scrape", run_booknetic),
        trigger="date",
        run_date=dt.datetime.now(dt.timezone.utc),
        id="booknetic_boot",
        replace_existing=True,
    )

    # Crons
    scheduler.add_job(
        lambda: run_with_job_meta("sheets_import", run_sheets),
        trigger="cron",
        minute="*/10",
        id="sheets_cron",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: run_with_job_meta("booknetic_scrape", run_booknetic),
        trigger="cron",
        minute="*/15",
        id="booknetic_cron",
        replace_existing=True,
    )

    print("[runner] Scheduler started. Cron: sheets @ *; booknetic @ */15 (boot run enabled)")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[runner] Stopping...")
        # Give some time for graceful shutdown when running locally
        time.sleep(0.5)


if __name__ == "__main__":
    main()


