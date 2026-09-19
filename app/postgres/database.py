from app.core.errors import IntegrationNotInstalled
from app.postgres.migrations import (
    POSTGRES_SCHEMA_VERSION,
    apply_postgres_migrations,
)


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise IntegrationNotInstalled(
            'Install PostgreSQL dependencies with pip install -e ".[postgres]".'
        ) from exc
    return psycopg, dict_row


def connect_postgres(database_url: str):
    if not database_url:
        raise ValueError("database_url is required for PostgreSQL.")
    psycopg, dict_row = _psycopg()
    return psycopg.connect(database_url, row_factory=dict_row)


def init_postgres_database(database_url: str) -> None:
    with connect_postgres(database_url) as connection:
        apply_postgres_migrations(connection)


def postgres_schema_version(database_url: str) -> int:
    with connect_postgres(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(MAX(version), 0) AS version "
                "FROM schema_migrations"
            )
            row = cursor.fetchone()
    return int(row["version"] or 0)
