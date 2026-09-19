from pathlib import Path

from app.core import database
from app.core.repositories import JobRepository, PostRepository
from app.services.queue import QueueService


def test_creator_queue_builds_stage_dag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stage-queue.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://www.xiaohongshu.com/explore/post-1",
        title="Post",
        post_type="video",
        raw={},
        platform_context={},
    )

    result = QueueService().enqueue_creator_pipeline(
        "creator-1",
        max_posts=1,
        idempotency_key="run-1",
    )

    jobs = JobRepository()
    creator_children = jobs.list_children(
        parent_job_id=result.parent_job_id
    )
    by_creator_type = {
        job["job_type"]: job for job in creator_children
    }
    assert set(by_creator_type) == {
        "POST_PIPELINE",
        "CREATOR_EXPORT",
    }

    post_job = by_creator_type["POST_PIPELINE"]
    creator_export = by_creator_type["CREATOR_EXPORT"]
    assert post_job["status"] == "WAITING"
    assert jobs.dependencies(job_id=creator_export["id"]) == [
        post_job["id"]
    ]

    stages = jobs.list_children(parent_job_id=post_job["id"])
    stage_types = {job["job_type"] for job in stages}
    assert stage_types == {
        "POST_DETAIL",
        "COMMENTS",
        "MEDIA_DOWNLOAD",
        "OCR",
        "STT",
        "VALIDATION",
        "EXPORT",
    }

    by_type = {job["job_type"]: job for job in stages}
    assert jobs.dependencies(job_id=by_type["POST_DETAIL"]["id"]) == []
    assert jobs.dependencies(job_id=by_type["COMMENTS"]["id"]) == [
        by_type["POST_DETAIL"]["id"]
    ]
    assert jobs.dependencies(job_id=by_type["MEDIA_DOWNLOAD"]["id"]) == [
        by_type["POST_DETAIL"]["id"]
    ]
    assert jobs.dependencies(job_id=by_type["OCR"]["id"]) == [
        by_type["MEDIA_DOWNLOAD"]["id"]
    ]
    assert jobs.dependencies(job_id=by_type["STT"]["id"]) == [
        by_type["MEDIA_DOWNLOAD"]["id"]
    ]

    validation_dependencies = set(
        jobs.dependencies(job_id=by_type["VALIDATION"]["id"])
    )
    assert validation_dependencies == {
        by_type["POST_DETAIL"]["id"],
        by_type["COMMENTS"]["id"],
        by_type["MEDIA_DOWNLOAD"]["id"],
        by_type["OCR"]["id"],
        by_type["STT"]["id"],
    }
    assert jobs.dependencies(job_id=by_type["EXPORT"]["id"]) == [
        by_type["VALIDATION"]["id"]
    ]
