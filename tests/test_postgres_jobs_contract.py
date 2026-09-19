import inspect

from app.postgres.jobs import CLAIM_SQL, PostgresJobRepository
from app.postgres.schema import POSTGRES_JOB_SCHEMA


def test_postgres_claim_uses_skip_locked() -> None:
    normalized = " ".join(CLAIM_SQL.split()).upper()

    assert "FOR UPDATE SKIP LOCKED" in normalized
    assert "RETURNING J.*" in normalized
    assert "DEPENDENCY.STATUS!='COMPLETE'" in normalized


def test_postgres_schema_has_job_dependencies() -> None:
    normalized = " ".join(POSTGRES_JOB_SCHEMA.split()).upper()

    assert "CREATE TABLE IF NOT EXISTS JOBS" in normalized
    assert "CREATE TABLE IF NOT EXISTS JOB_DEPENDENCIES" in normalized
    assert "JSONB" in normalized
    assert "TIMESTAMPTZ" in normalized


def test_postgres_repository_exposes_core_contract() -> None:
    methods = {
        name
        for name, member in inspect.getmembers(
            PostgresJobRepository,
            predicate=inspect.isfunction,
        )
    }

    assert {
        "enqueue",
        "claim_next",
        "heartbeat",
        "recover_expired_leases",
        "resolve_failed_dependencies",
        "schedule_retry",
        "mark_waiting",
        "mark_complete",
        "mark_failed",
        "get",
        "reconcile_ancestors",
    } <= methods
