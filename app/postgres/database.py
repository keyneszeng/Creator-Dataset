from app.core.errors import IntegrationNotInstalled
from app.postgres.schema import (
    POSTGRES_CONTENT_SCHEMA,
    POSTGRES_CREATOR_POST_SCHEMA,
    POSTGRES_JOB_SCHEMA,
    POSTGRES_REFRESH_SCHEMA,
)

POSTGRES_SCHEMA_VERSION = 1


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
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute(POSTGRES_CREATOR_POST_SCHEMA)
            cursor.execute(POSTGRES_CONTENT_SCHEMA)
            cursor.execute(POSTGRES_JOB_SCHEMA)
            cursor.execute(POSTGRES_REFRESH_SCHEMA)
            cursor.execute("""
                INSERT INTO schema_migrations (version)
                VALUES (%s)
                ON CONFLICT(version) DO NOTHING
            """, (POSTGRES_SCHEMA_VERSION,))


def postgres_schema_version(database_url: str) -> int:
    with connect_postgres(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(MAX(version), 0) AS version "
                "FROM schema_migrations"
            )
            row = cursor.fetchone()
    return int(row["version"] or 0)
