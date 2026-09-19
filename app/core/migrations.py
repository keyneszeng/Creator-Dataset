import sqlite3
from collections.abc import Callable

CURRENT_SCHEMA_VERSION = 4

Migration = Callable[[sqlite3.Connection], None]


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_column(
    connection: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    if column not in _columns(connection, table):
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def migration_001_post_detail_context(connection: sqlite3.Connection) -> None:
    _ensure_column(
        connection,
        table="posts",
        column="platform_context_json",
        definition="TEXT",
    )
    _ensure_column(
        connection,
        table="posts",
        column="detail_raw_json",
        definition="TEXT",
    )


def migration_002_incremental_refresh(connection: sqlite3.Connection) -> None:
    for column, definition in (
        ("discovery_fingerprint", "TEXT"),
        ("detail_fingerprint", "TEXT"),
        ("content_fingerprint", "TEXT"),
        ("media_fingerprint", "TEXT"),
        ("engagement_fingerprint", "TEXT"),
        ("comments_fingerprint", "TEXT"),
        ("last_discovered_at", "DATETIME"),
        ("last_refreshed_at", "DATETIME"),
    ):
        _ensure_column(
            connection,
            table="posts",
            column=column,
            definition=definition,
        )


def migration_003_durable_jobs(connection: sqlite3.Connection) -> None:
    for column, definition in (
        ("parent_job_id", "INTEGER"),
        ("idempotency_key", "TEXT"),
        ("payload_json", "TEXT"),
        ("priority", "INTEGER NOT NULL DEFAULT 100"),
        ("attempt", "INTEGER NOT NULL DEFAULT 0"),
        ("max_attempts", "INTEGER NOT NULL DEFAULT 5"),
        ("lease_owner", "TEXT"),
        ("lease_expires_at", "DATETIME"),
        ("heartbeat_at", "DATETIME"),
    ):
        _ensure_column(
            connection,
            table="jobs",
            column=column,
            definition=definition,
        )

    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency "
        "ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_runnable "
        "ON jobs(status, next_retry_at, priority, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_parent "
        "ON jobs(parent_job_id, status)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS job_dependencies (
            job_id INTEGER NOT NULL,
            depends_on_job_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(job_id, depends_on_job_id),
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY(depends_on_job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_dependencies_target "
        "ON job_dependencies(depends_on_job_id, job_id)"
    )


def migration_004_media_storage(connection: sqlite3.Connection) -> None:
    for column, definition in (
        ("storage_backend", "TEXT"),
        ("storage_key", "TEXT"),
        ("is_active", "BOOLEAN NOT NULL DEFAULT 1"),
    ):
        _ensure_column(
            connection,
            table="media",
            column=column,
            definition=definition,
        )


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, migration_001_post_detail_context),
    (2, migration_002_incremental_refresh),
    (3, migration_003_durable_jobs),
    (4, migration_004_media_storage),
]


def apply_migrations(connection: sqlite3.Connection) -> int:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    rows = connection.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()
    applied = {int(row["version"]) for row in rows}

    for version, migration in MIGRATIONS:
        if version in applied:
            continue
        migration(connection)
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (version,),
        )

    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"])
