import sqlite3
from collections.abc import Callable

CURRENT_SCHEMA_VERSION = 7

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


def migration_005_saas_access(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            last_used_at DATETIME,
            revoked_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_api_keys_user
        ON api_keys(user_id, revoked_at);

        CREATE TABLE IF NOT EXISTS credit_ledger (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            bucket TEXT NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL,
            reference_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_bucket
        ON credit_ledger(user_id, bucket, id);

        CREATE TABLE IF NOT EXISTS dataset_entitlements (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            source TEXT NOT NULL,
            granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            UNIQUE(user_id, platform, post_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_entitlements_user
        ON dataset_entitlements(user_id, granted_at);

        CREATE TABLE IF NOT EXISTS creator_submissions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            submitted_url TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_creator_submissions_user
        ON creator_submissions(user_id, created_at);
    """)


def migration_006_dataset_artifacts(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS dataset_artifacts (
            id INTEGER PRIMARY KEY,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            dataset_schema_version TEXT NOT NULL,
            storage_backend TEXT NOT NULL,
            export_prefix TEXT NOT NULL,
            artifacts_json TEXT NOT NULL,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform, post_id, dataset_schema_version)
        );

        CREATE INDEX IF NOT EXISTS idx_dataset_artifacts_post
        ON dataset_artifacts(platform, post_id, generated_at);
    """)


def migration_007_billing_events(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS billing_events (
            id INTEGER PRIMARY KEY,
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            credits INTEGER NOT NULL DEFAULT 0,
            amount_minor INTEGER,
            currency TEXT,
            payload_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider, event_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_billing_events_user
        ON billing_events(user_id, created_at);
    """)


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, migration_001_post_detail_context),
    (2, migration_002_incremental_refresh),
    (3, migration_003_durable_jobs),
    (4, migration_004_media_storage),
    (5, migration_005_saas_access),
    (6, migration_006_dataset_artifacts),
    (7, migration_007_billing_events),
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
