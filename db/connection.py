import os
from contextlib import contextmanager
from typing import Iterator, Optional

from psycopg_pool import ConnectionPool


_pool: Optional[ConnectionPool] = None


def _create_pool() -> ConnectionPool:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está definido en el entorno")
    # Default small pool; Railway free tiers are constrained
    return ConnectionPool(conninfo=database_url, min_size=1, max_size=5, open=True)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = _create_pool()
    return _pool


@contextmanager
def get_connection():
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


