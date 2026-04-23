import os
from contextlib import contextmanager
from typing import Iterator, Optional

from psycopg_pool import ConnectionPool


_pool: Optional[ConnectionPool] = None


def _conninfo_with_connect_timeout(conninfo: str) -> str:
    """Evita cuelgues indefinidos si Postgres no responde (p. ej. red / credenciales)."""
    if "connect_timeout=" in conninfo:
        return conninfo
    raw = (os.getenv("PG_CONNECT_TIMEOUT") or "20").strip()
    try:
        sec = max(5, min(120, int(raw)))
    except ValueError:
        sec = 20
    sep = "&" if "?" in conninfo else "?"
    return f"{conninfo}{sep}connect_timeout={sec}"


def _create_pool() -> ConnectionPool:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está definido en el entorno")
    conninfo = _conninfo_with_connect_timeout(database_url.strip())
    # Default small pool; Railway free tiers are constrained
    return ConnectionPool(conninfo=conninfo, min_size=1, max_size=5, open=True)


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


