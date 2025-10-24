import os
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from db.utils import run_with_job_meta, print_db_identity
from db.migrate import ensure_schema
from jobs.job_import_sheets import run as run_sheets
from jobs.job_scrape_booknetic import run as run_booknetic


def main() -> None:
    load_dotenv()  # no-op in Railway, useful local

    # Ensure DB schema exists before scheduling jobs
    print_db_identity()
    ensure_schema()

    scheduler = BlockingScheduler(timezone=os.getenv("TZ", "UTC"))

    scheduler.add_job(lambda: run_with_job_meta("sheets_import", run_sheets), trigger="cron", minute="*")
    scheduler.add_job(lambda: run_with_job_meta("booknetic_scrape", run_booknetic), trigger="cron", minute="*/")

    print("[runner] Scheduler started. Cron: sheets @ *; booknetic @ */15")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[runner] Stopping...")
        # Give some time for graceful shutdown when running locally
        time.sleep(0.5)


if __name__ == "__main__":
    main()


