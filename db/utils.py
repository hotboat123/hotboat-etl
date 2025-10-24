import datetime as dt
import traceback
from typing import Any, Callable, Dict, Iterable, List, Sequence

from psycopg import sql

from db.connection import get_connection


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def upsert_many(
    table: str,
    rows: Iterable[Dict[str, Any]],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str],
) -> int:
    rows_list = [r for r in rows if r]
    if not rows_list:
        return 0

    all_columns: List[str] = list({k for row in rows_list for k in row.keys()})
    # Ensure conflict and update columns exist in the insert list
    for c in set(conflict_columns).union(update_columns):
        if c not in all_columns:
            all_columns.append(c)

    insert_stmt = sql.SQL(
        """
        INSERT INTO {table} ({cols})
        VALUES {values}
        ON CONFLICT ({conflict}) DO UPDATE SET {updates}
        """
    ).format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in all_columns),
        values=sql.SQL(", ").join(
            sql.SQL("(")
            + sql.SQL(", ").join(sql.Placeholder() for _ in all_columns)
            + sql.SQL(")")
            for _ in rows_list
        ),
        conflict=sql.SQL(", ").join(sql.Identifier(c) for c in conflict_columns),
        updates=sql.SQL(", ").join(
            sql.Identifier(c) + sql.SQL(" = EXCLUDED.") + sql.Identifier(c)
            for c in update_columns
        ),
    )

    flat_params: List[Any] = []
    for r in rows_list:
        for c in all_columns:
            flat_params.append(r.get(c))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(insert_stmt, flat_params)
        conn.commit()
    return len(rows_list)


# Job meta logging
def record_job_start(job_name: str) -> int:
    started_at = now_utc()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_runs (job_name, status, started_at)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (job_name, "running", started_at),
            )
            job_run_id = cur.fetchone()[0]
        conn.commit()
    return job_run_id


def record_job_end(job_run_id: int, row_count: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_runs
                SET status = %s, finished_at = %s, row_count = %s
                WHERE id = %s
                """,
                ("success", now_utc(), row_count, job_run_id),
            )
        conn.commit()


def record_job_error(job_run_id: int, err: BaseException) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_runs
                SET status = %s, finished_at = %s, error = %s
                WHERE id = %s
                """,
                ("error", now_utc(), f"{type(err).__name__}: {err}\n{traceback.format_exc()}", job_run_id),
            )
        conn.commit()


def run_with_job_meta(job_name: str, fn: Callable[[], int]) -> None:
    job_run_id = record_job_start(job_name)
    try:
        row_count = int(fn() or 0)
        record_job_end(job_run_id, row_count)
        print(f"[job {job_name}] success rows={row_count}")
    except BaseException as e:  # noqa: BLE001
        record_job_error(job_run_id, e)
        print(f"[job {job_name}] error: {e}")
        raise


