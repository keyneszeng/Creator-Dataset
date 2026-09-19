import os
from pathlib import Path

import pytest

from app.core.readiness import check_readiness
from app.core.settings import Settings
from app.postgres.database import init_postgres_database
from app.postgres.jobs import PostgresJobRepository
from app.repositories.factory import (
    create_job_repository,
    create_post_repository,
)
from app.services.queue import QueueService


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def test_postgres_backend_drives_queue_service(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="postgres",
        database_url=str(DATABASE_URL),
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
    )
    init_postgres_database(str(DATABASE_URL))

    jobs = create_job_repository(settings)
    posts = create_post_repository(settings)

    assert isinstance(jobs, PostgresJobRepository)

    with jobs._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE job_dependencies, jobs, posts, creators "
                "RESTART IDENTITY CASCADE"
            )

    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="Post",
        post_type="normal",
        raw={},
        platform_context={},
    )

    result = QueueService(
        jobs=jobs,
        posts=posts,
    ).enqueue_creator_pipeline(
        "creator-1",
        max_posts=1,
        run_comments=False,
        run_media=False,
        run_ocr=False,
        run_stt=False,
        export=False,
        idempotency_key="postgres-app-test",
    )

    tree = jobs.job_tree(root_job_id=result.parent_job_id)
    types = {item["job_type"] for item in tree}

    assert result.posts_enqueued == 1
    assert "CREATOR_PIPELINE" in types
    assert "POST_PIPELINE" in types
    assert "POST_DETAIL" in types
    assert "VALIDATION" in types

    monkeypatch.setattr(
        "app.core.readiness.get_settings",
        lambda: settings,
    )
    readiness = check_readiness()
    assert readiness["ready"] is True
    assert readiness["checks"]["database"]["backend"] == "postgres"
