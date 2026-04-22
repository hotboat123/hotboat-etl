import datetime as dt
import traceback
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from psycopg import sql
from psycopg.types.json import Json

from db.connection import get_connection


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def replace_all(
    table: str,
    rows: Iterable[Dict[str, Any]],
) -> int:
    """
    Truncate table and insert all rows (full replacement).
    Use this when the CSV export contains ALL data and we want
    an exact mirror of the source system.
    """
    rows_list = [r for r in rows if r]
    if not rows_list:
        print(f"[db] No rows to insert into {table}, skipping truncate")
        return 0

    all_columns: List[str] = list({k for row in rows_list for k in row.keys()})

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 1: Truncate table
            truncate_stmt = sql.SQL("TRUNCATE TABLE {table} CASCADE").format(
                table=sql.Identifier(table)
            )
            print(f"[db] Truncating table {table}...")
            cur.execute(truncate_stmt)
            
            # Step 2: Insert all rows in batches
            batch_size = 500
            total_inserted = 0
            
            for i in range(0, len(rows_list), batch_size):
                batch = rows_list[i : i + batch_size]
                
                insert_stmt = sql.SQL(
                    "INSERT INTO {table} ({cols}) VALUES {values}"
                ).format(
                    table=sql.Identifier(table),
                    cols=sql.SQL(", ").join(sql.Identifier(c) for c in all_columns),
                    values=sql.SQL(", ").join(
                        sql.SQL("(")
                        + sql.SQL(", ").join(sql.Placeholder() for _ in all_columns)
                        + sql.SQL(")")
                        for _ in batch
                    ),
                )

                flat_params: List[Any] = []
                for r in batch:
                    for c in all_columns:
                        v = r.get(c)
                        if isinstance(v, (dict, list)):
                            v = Json(v)
                        flat_params.append(v)

                cur.execute(insert_stmt, flat_params)
                total_inserted += len(batch)
                print(f"[db] Inserted {total_inserted}/{len(rows_list)} rows into {table}")
            
        conn.commit()
        print(f"[db] ✅ {table} replaced with {len(rows_list)} rows")

    return len(rows_list)


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
                v = r.get(c)
                if isinstance(v, (dict, list)):
                    v = Json(v)
                flat_params.append(v)

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


