from pathlib import Path

from app.core import database
from app.core.repositories import JobRepository


def test_repair_reopens_target_and_downstream_jobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "repair.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    jobs = JobRepository()
    creator = jobs.enqueue(job_type="CREATOR_PIPELINE")
    jobs.mark_waiting(job_id=creator)

    post = jobs.enqueue(
        job_type="POST_PIPELINE",
        parent_job_id=creator,
    )
    jobs.mark_waiting(job_id=post)

    media = jobs.enqueue(
        job_type="MEDIA_DOWNLOAD",
        parent_job_id=post,
    )
    ocr = jobs.enqueue(
        job_type="OCR",
        parent_job_id=post,
        depends_on=[media],
    )
    validation = jobs.enqueue(
        job_type="VALIDATION",
        parent_job_id=post,
        depends_on=[ocr],
    )

    jobs.mark_failed(job_id=media, error="download failed")
    jobs.resolve_failed_dependencies()
    jobs.resolve_failed_dependencies()
    jobs.reconcile_ancestors(job_id=media)

    assert jobs.get(job_id=ocr)["status"] == "PARTIAL"
    assert jobs.get(job_id=validation)["status"] == "PARTIAL"
    assert jobs.get(job_id=post)["status"] == "PARTIAL"
    assert jobs.get(job_id=creator)["status"] == "PARTIAL"

    repaired = jobs.repair_subgraph(job_id=media)

    assert set(repaired) == {media, ocr, validation}
    assert jobs.get(job_id=media)["status"] == "PENDING"
    assert jobs.get(job_id=ocr)["status"] == "PENDING"
    assert jobs.get(job_id=validation)["status"] == "PENDING"
    assert jobs.get(job_id=post)["status"] == "WAITING"
    assert jobs.get(job_id=creator)["status"] == "WAITING"
