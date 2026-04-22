"""Inspect marketing_costs_daily in Postgres (view vs matview + definition)."""
import os
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
                SELECT c.relkind, n.nspname, c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'marketing_costs_daily'
                """
            )
            row = cur.fetchone()
            if not row:
                print("No existe objeto marketing_costs_daily en la base.")
                return
            kind, schema, name = row
            kinds = {
                "r": "tabla (heap)",
                "v": "vista normal",
                "m": "vista materializada",
            }
            print(f"Tipo: {kinds.get(kind, kind)}  ({schema}.{name})")

            if kind == "v":
                cur.execute(
                    """
                    SELECT pg_get_viewdef(
                        (quote_ident(%s) || '.' || quote_ident(%s))::regclass,
                        true
                    )
                    """,
                    (schema, name),
                )
                (defn,) = cur.fetchone()
                print("\n--- Definición de la vista ---\n")
                print(defn)
            elif kind == "m":
                cur.execute(
                    """
                    SELECT pg_get_viewdef(
                        (quote_ident(%s) || '.' || quote_ident(%s))::regclass,
                        true
                    )
                    """,
                    (schema, name),
                )
                (defn,) = cur.fetchone()
                print("\n--- Definición (query) ---\n")
                print(defn)
                print(
                    "\nLas vistas materializadas NO se actualizan solas: ejecuta "
                    "REFRESH MATERIALIZED VIEW ... (o CONCURRENTLY si tiene índice único)."
                )


if __name__ == "__main__":
    main()
