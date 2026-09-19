from pathlib import Path

from app.core import database
from app.core.repositories import JobRepository


def test_job_with_unfinished_dependency_is_not_claimed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "deps.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    jobs = JobRepository()
    first = jobs.enqueue(job_type="POST_DETAIL")
    second = jobs.enqueue(
        job_type="COMMENTS",
        depends_on=[first],
    )

    claimed = jobs.claim_next(worker_id="w1")
    assert claimed["id"] == first

    jobs.mark_complete(job_id=first)
    claimed = jobs.claim_next(worker_id="w1")
    assert claimed["id"] == second


def test_failed_dependency_marks_downstream_partial(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "failed-deps.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    jobs = JobRepository()
    first = jobs.enqueue(job_type="MEDIA_DOWNLOAD")
    second = jobs.enqueue(
        job_type="OCR",
        depends_on=[first],
    )
    jobs.mark_failed(job_id=first, error="download failed")

    assert jobs.resolve_failed_dependencies() == 1
    assert jobs.get(job_id=second)["status"] == "PARTIAL"
