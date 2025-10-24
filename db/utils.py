import datetime as dt
import traceback
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

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

    # Deduplicate by conflict key (last one wins) to avoid 21000 error when a batch
    # contains multiple rows targeting the same constraint.
    if conflict_columns:
        unique_map: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        for r in rows_list:
            key = tuple(r.get(c) for c in conflict_columns)
            # Skip rows that don't have full conflict key
            if any(v is None for v in key):
                continue
            unique_map[key] = r
        deduped = list(unique_map.values())
        if len(deduped) != len(rows_list):
            try:
                print(f"[db] deduplicated {len(rows_list) - len(deduped)} rows on keys {list(conflict_columns)}")
            except Exception:
                pass
        rows_list = deduped

    all_columns: List[str] = list({k for row in rows_list for k in row.keys()})
    # Ensure conflict and update columns exist in the insert list
    for c in set(conflict_columns).union(update_columns):
        if c not in all_columns:
            all_columns.append(c)

    def execute_batch(batch: List[Dict[str, Any]]) -> None:
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
                for _ in batch
            ),
            conflict=sql.SQL(", ").join(sql.Identifier(c) for c in conflict_columns),
            updates=sql.SQL(", ").join(
                sql.Identifier(c) + sql.SQL(" = EXCLUDED.") + sql.Identifier(c)
                for c in update_columns
            ),
        )

        flat_params: List[Any] = []
        for r in batch:
            for c in all_columns:
                flat_params.append(r.get(c))

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(insert_stmt, flat_params)
            conn.commit()

    # Insert in chunks to avoid very large single statements/param lists
    batch_size = 500
    for i in range(0, len(rows_list), batch_size):
        execute_batch(rows_list[i : i + batch_size])

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


def print_db_identity() -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select current_database(), inet_server_addr(), inet_server_port()")
                db, addr, port = cur.fetchone()
                print(f"[db] connected to db={db} host={addr} port={port}")
    except Exception as e:  # noqa: BLE001
        print(f"[db] identity check failed: {e}")


