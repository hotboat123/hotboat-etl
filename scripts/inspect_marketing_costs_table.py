"""Describe marketing_costs table (columns + sample)."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv

load_dotenv(_root / ".env")

from db.connection import get_connection


def main() -> None:
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'marketing_costs'
                ORDER BY ordinal_position
                """
            )
            print("Columnas marketing_costs:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}")
            cur.execute("SELECT max(cost_date) FROM marketing_costs")
            print("max(cost_date):", cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM marketing_costs")
            print("rows:", cur.fetchone()[0])


if __name__ == "__main__":
    main()
