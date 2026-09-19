import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.postgres.jobs import PostgresJobRepository


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def _repository() -> PostgresJobRepository:
    repository = PostgresJobRepository(str(DATABASE_URL))
    repository.init_schema()
    return repository


def _reset(repository: PostgresJobRepository) -> None:
    with repository._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE job_dependencies, jobs "
                "RESTART IDENTITY CASCADE"
            )


def test_concurrent_workers_claim_distinct_jobs() -> None:
    repository = _repository()
    _reset(repository)

    first = repository.enqueue(job_type="TEST", priority=100)
    second = repository.enqueue(job_type="TEST", priority=100)

    def claim(worker_id: str):
        return _repository().claim_next(
            worker_id=worker_id,
            lease_seconds=60,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(
            executor.map(claim, ["worker-a", "worker-b"])
        )

    ids = {int(job["id"]) for job in claimed if job is not None}

    assert ids == {first, second}
    assert all(job["status"] == "RUNNING" for job in claimed)


def test_dependency_blocks_until_complete() -> None:
    repository = _repository()
    _reset(repository)

    detail = repository.enqueue(job_type="POST_DETAIL")
    comments = repository.enqueue(
        job_type="COMMENTS",
        depends_on=[detail],
    )

    claimed = repository.claim_next(worker_id="worker-a")
    assert claimed["id"] == detail

    assert repository.claim_next(worker_id="worker-b") is None

    repository.mark_complete(job_id=detail)

    claimed = repository.claim_next(worker_id="worker-b")
    assert claimed["id"] == comments


def test_expired_postgres_lease_requeues() -> None:
    repository = _repository()
    _reset(repository)

    job_id = repository.enqueue(
        job_type="TEST",
        max_attempts=2,
    )
    repository.claim_next(worker_id="worker-a", lease_seconds=60)

    with repository._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE jobs "
                "SET lease_expires_at=NOW() - INTERVAL '1 second' "
                "WHERE id=%s",
                (job_id,),
            )

    assert repository.recover_expired_leases() == 1
    assert repository.get(job_id=job_id)["status"] == "RETRY"
