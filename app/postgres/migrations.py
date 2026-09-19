from collections.abc import Callable
from typing import Any

from app.postgres.schema import (
    POSTGRES_CONTENT_SCHEMA,
    POSTGRES_CREATOR_POST_SCHEMA,
    POSTGRES_JOB_SCHEMA,
    POSTGRES_REFRESH_SCHEMA,
)

POSTGRES_SCHEMA_VERSION = 2
POSTGRES_MIGRATION_LOCK_KEY = 48392178

Migration = Callable[[Any], None]


def migration_001_bootstrap(cursor) -> None:
    cursor.execute(POSTGRES_CREATOR_POST_SCHEMA)
    cursor.execute(POSTGRES_CONTENT_SCHEMA)
    cursor.execute(POSTGRES_JOB_SCHEMA)
    cursor.execute(POSTGRES_REFRESH_SCHEMA)


def migration_002_cloud_runtime_indexes(cursor) -> None:
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_lease_expiry
        ON jobs(status, lease_expires_at)
        WHERE status='RUNNING'
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_retry_due
        ON jobs(status, next_retry_at, priority, created_at)
        WHERE status IN ('PENDING', 'RETRY')
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_refresh_runs_creator_created
        ON refresh_runs(platform, creator_id, created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workers_current_job
        ON workers(current_job_id)
        WHERE current_job_id IS NOT NULL
    """)


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, migration_001_bootstrap),
    (2, migration_002_cloud_runtime_indexes),
]


def apply_postgres_migrations(connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Transaction-scoped lock prevents multiple API replicas from
        # running schema upgrades concurrently during a rolling deploy.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (POSTGRES_MIGRATION_LOCK_KEY,),
        )

        cursor.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        applied = {int(row["version"]) for row in cursor.fetchall()}

        for version, migration in MIGRATIONS:
            if version in applied:
                continue
            migration(cursor)
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )

        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) AS version "
            "FROM schema_migrations"
        )
        row = cursor.fetchone()
        return int(row["version"] or 0)
