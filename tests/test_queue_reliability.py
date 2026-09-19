from pathlib import Path

from app.core import database
from app.core.repositories import JobRepository


def _settings(tmp_path: Path):
    class Settings:
        database_path = tmp_path / "queue.sqlite3"
    return Settings()


def test_expired_lease_is_requeued_then_terminal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    database.init_database(settings.database_path)
    monkeypatch.setattr(database, "get_settings", lambda: settings)

    jobs = JobRepository()
    job_id = jobs.enqueue(
        job_type="TEST",
        max_attempts=2,
    )

    claimed = jobs.claim_next(worker_id="worker-1", lease_seconds=60)
    assert claimed["id"] == job_id
    assert claimed["attempt"] == 1

    with database.db_session(settings.database_path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=datetime('now', '-1 second') "
            "WHERE id=?",
            (job_id,),
        )

    assert jobs.recover_expired_leases() == 1
    assert jobs.get(job_id=job_id)["status"] == "RETRY"

    claimed = jobs.claim_next(worker_id="worker-2", lease_seconds=60)
    assert claimed["attempt"] == 2

    with database.db_session(settings.database_path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=datetime('now', '-1 second') "
            "WHERE id=?",
            (job_id,),
        )

    assert jobs.recover_expired_leases() == 1
    job = jobs.get(job_id=job_id)
    assert job["status"] == "FAILED"
    assert job["completed_at"] is not None


def test_parent_becomes_partial_when_child_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    database.init_database(settings.database_path)
    monkeypatch.setattr(database, "get_settings", lambda: settings)

    jobs = JobRepository()
    parent = jobs.enqueue(job_type="CREATOR_PIPELINE")
    jobs.mark_waiting(job_id=parent)

    child_a = jobs.enqueue(
        job_type="POST_PIPELINE",
        parent_job_id=parent,
    )
    child_b = jobs.enqueue(
        job_type="POST_PIPELINE",
        parent_job_id=parent,
    )

    jobs.mark_complete(job_id=child_a)
    jobs.mark_failed(job_id=child_b, error="boom")

    summary = jobs.reconcile_parent(parent_job_id=parent)

    assert summary["TOTAL"] == 2
    assert jobs.get(job_id=parent)["status"] == "PARTIAL"
