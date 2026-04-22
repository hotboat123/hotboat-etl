"""One-off: list distinct action_type from meta_ads_insights (run from repo root)."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv

load_dotenv(_root / ".env")

from db.connection import get_connection

SQL_ACTIONS = """
SELECT DISTINCT elem->>'action_type' AS action_type
FROM meta_ads_insights,
     jsonb_array_elements(COALESCE(actions, '[]'::jsonb)) AS elem
WHERE elem->>'action_type' IS NOT NULL
ORDER BY 1;
"""

SQL_COSTS = """
SELECT DISTINCT elem->>'action_type' AS action_type
FROM meta_ads_insights,
     jsonb_array_elements(COALESCE(cost_per_action_type, '[]'::jsonb)) AS elem
WHERE elem->>'action_type' IS NOT NULL
ORDER BY 1;
"""


def main() -> None:
    with get_connection() as c:
        with c.cursor() as cur:
            print("=== actions ===")
            cur.execute(SQL_ACTIONS)
            for (t,) in cur.fetchall():
                print(t)
            print()
            print("=== cost_per_action_type ===")
            cur.execute(SQL_COSTS)
            for (t,) in cur.fetchall():
                print(t)


if __name__ == "__main__":
    main()
