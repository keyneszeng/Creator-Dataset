from threading import Lock
from typing import Any

from app.core.errors import IntegrationNotInstalled


_POOLS: dict[str, Any] = {}
_LOCK = Lock()


def _pool_class():
    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise IntegrationNotInstalled(
            'Install PostgreSQL dependencies with pip install -e ".[postgres]".'
        ) from exc
    return ConnectionPool, dict_row


def get_postgres_pool(
    database_url: str,
    *,
    min_size: int = 1,
    max_size: int = 10,
):
    if not database_url:
        raise ValueError("database_url is required for PostgreSQL.")

    with _LOCK:
        pool = _POOLS.get(database_url)
        if pool is not None:
            return pool

        ConnectionPool, dict_row = _pool_class()
        pool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        _POOLS[database_url] = pool
        return pool


def pooled_connection(database_url: str):
    return get_postgres_pool(database_url).connection()


def close_postgres_pools() -> None:
    with _LOCK:
        pools = list(_POOLS.values())
        _POOLS.clear()

    for pool in pools:
        pool.close()
