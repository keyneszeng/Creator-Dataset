from pathlib import Path

import pytest

from app.core import database
from app.core.jobs import RetryPolicy
from app.core.repositories import JobRepository
from app.worker import DurableWorker


@pytest.mark.asyncio
async def test_worker_claims_and_completes_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "worker.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path
        worker_lease_seconds = 30
        worker_heartbeat_seconds = 5
        worker_poll_seconds = 0.01

    settings = _Settings()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.get_settings", lambda: settings)

    jobs = JobRepository()
    handled: list[int] = []

    async def handler(job):
        handled.append(int(job["id"]))

    job_id = jobs.enqueue(
        job_type="TEST",
        idempotency_key="test-job",
        payload={"hello": "world"},
    )

    worker = DurableWorker(
        worker_id="test-worker",
        jobs=jobs,
        handlers={"TEST": handler},
        retry_policy=RetryPolicy(
            base_seconds=1,
            max_seconds=1,
            jitter_ratio=0,
        ),
    )

    assert await worker.run_once() is True
    assert handled == [job_id]

    job = jobs.get(job_id=job_id)
    assert job["status"] == "COMPLETE"
    assert job["attempt"] == 1
    assert job["payload"] == {"hello": "world"}


def test_enqueue_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "idempotent.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    jobs = JobRepository()
    first = jobs.enqueue(
        job_type="TEST",
        idempotency_key="same-key",
    )
    second = jobs.enqueue(
        job_type="TEST",
        idempotency_key="same-key",
    )

    assert first == second
