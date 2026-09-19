from collections.abc import Callable
from typing import Any

from app.postgres.schema import (
    POSTGRES_CONTENT_SCHEMA,
    POSTGRES_CREATOR_POST_SCHEMA,
    POSTGRES_JOB_SCHEMA,
    POSTGRES_REFRESH_SCHEMA,
)

POSTGRES_SCHEMA_VERSION = 7
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


def migration_003_saas_access(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            last_used_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_api_keys_user
        ON api_keys(user_id, revoked_at);

        CREATE TABLE IF NOT EXISTS credit_ledger (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            bucket TEXT NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL,
            reference_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_bucket
        ON credit_ledger(user_id, bucket, id);

        CREATE TABLE IF NOT EXISTS dataset_entitlements (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            source TEXT NOT NULL,
            granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ,
            UNIQUE(user_id, platform, post_id)
        );

        CREATE INDEX IF NOT EXISTS idx_entitlements_user
        ON dataset_entitlements(user_id, granted_at DESC);

        CREATE TABLE IF NOT EXISTS creator_submissions (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            submitted_url TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_creator_submissions_user
        ON creator_submissions(user_id, created_at DESC);
    """)


def migration_004_dataset_artifacts(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_artifacts (
            id BIGSERIAL PRIMARY KEY,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            dataset_schema_version TEXT NOT NULL,
            storage_backend TEXT NOT NULL,
            export_prefix TEXT NOT NULL,
            artifacts_json JSONB NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(platform, post_id, dataset_schema_version)
        );

        CREATE INDEX IF NOT EXISTS idx_dataset_artifacts_post
        ON dataset_artifacts(platform, post_id, generated_at DESC);
    """)


def migration_005_billing_events(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS billing_events (
            id BIGSERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            credits INTEGER NOT NULL DEFAULT 0,
            amount_minor BIGINT,
            currency TEXT,
            payload_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(provider, event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_billing_events_user
        ON billing_events(user_id, created_at DESC);
    """)


def migration_006_payment_orders(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_orders (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            merchant_order_no TEXT NOT NULL,
            provider_order_id TEXT,
            product_code TEXT NOT NULL,
            credits INTEGER NOT NULL,
            amount_minor BIGINT NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            client_context_json JSONB,
            expires_at TIMESTAMPTZ,
            paid_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(provider, merchant_order_no)
        );

        CREATE INDEX IF NOT EXISTS idx_payment_orders_user
        ON payment_orders(user_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_payment_orders_provider_status
        ON payment_orders(provider, status, created_at DESC);

        CREATE TABLE IF NOT EXISTS payment_identities (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            application_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(provider, application_id, subject_id),
            UNIQUE(user_id, provider, application_id)
        );

        CREATE INDEX IF NOT EXISTS idx_payment_identities_user
        ON payment_identities(user_id, provider);
    """)


def migration_007_llm_organization(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_connections (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            label TEXT NOT NULL,
            model TEXT NOT NULL,
            base_url TEXT NOT NULL,
            secret_ciphertext TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, label)
        );

        CREATE INDEX IF NOT EXISTS idx_llm_connections_user
        ON llm_connections(user_id, enabled);

        CREATE TABLE IF NOT EXISTS llm_organization_runs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            post_id TEXT NOT NULL,
            connection_id BIGINT NOT NULL
                REFERENCES llm_connections(id) ON DELETE CASCADE,
            task TEXT NOT NULL,
            custom_instruction TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            input_schema_version TEXT NOT NULL,
            result_json JSONB,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_llm_runs_user_post
        ON llm_organization_runs(user_id, post_id, id DESC);

        CREATE INDEX IF NOT EXISTS idx_llm_runs_status
        ON llm_organization_runs(status, created_at);
    """)


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, migration_001_bootstrap),
    (2, migration_002_cloud_runtime_indexes),
    (3, migration_003_saas_access),
    (4, migration_004_dataset_artifacts),
    (5, migration_005_billing_events),
    (6, migration_006_payment_orders),
    (7, migration_007_llm_organization),
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
