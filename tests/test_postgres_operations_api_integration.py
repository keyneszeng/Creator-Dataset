import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import app
from app.postgres.database import init_postgres_database
from app.postgres.jobs import PostgresJobRepository
from app.postgres.refresh import PostgresRefreshScheduleRepository


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def test_job_tree_repair_and_schedule_resume_use_postgres(
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

    jobs = PostgresJobRepository(str(DATABASE_URL))
    schedules = PostgresRefreshScheduleRepository(str(DATABASE_URL))

    with jobs._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE job_dependencies, jobs, refresh_schedules "
                "RESTART IDENTITY CASCADE"
            )

    parent = jobs.enqueue(job_type="POST_PIPELINE")
    jobs.mark_waiting(job_id=parent)
    stage = jobs.enqueue(
        job_type="OCR",
        parent_job_id=parent,
    )
    jobs.mark_failed(job_id=stage, error="ocr failed")
    jobs.reconcile_ancestors(job_id=stage)

    schedule_id = schedules.upsert(
        platform="xiaohongshu",
        creator_id="creator-1",
        interval_minutes=1440,
        max_pages=3,
        max_recent_posts=30,
        stop_after_unchanged_pages=2,
        next_run_at="2099-01-01 00:00:00+00",
        enabled=False,
    )

    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.api.routes.create_job_repository",
        lambda: jobs,
    )
    monkeypatch.setattr(
        "app.api.routes.create_refresh_schedule_repository",
        lambda: schedules,
    )

    with TestClient(app) as client:
        tree = client.get(f"/api/jobs/{parent}/tree")
        repair = client.post(f"/api/jobs/{stage}/repair")
        resume = client.post(
            f"/api/refresh-schedules/{schedule_id}/resume"
        )

    assert tree.status_code == 200
    assert {item["job_type"] for item in tree.json()["jobs"]} == {
        "POST_PIPELINE",
        "OCR",
    }

    assert repair.status_code == 200
    assert stage in repair.json()["repaired_job_ids"]
    assert jobs.get(job_id=stage)["status"] == "PENDING"
    assert jobs.get(job_id=parent)["status"] == "WAITING"

    assert resume.status_code == 200
    schedule = schedules.list_all()[0]
    assert schedule["enabled"] is True
