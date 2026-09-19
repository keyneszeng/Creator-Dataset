from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.repositories import JobRepository
from app.main import app


def test_get_job_endpoint(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path
        data_dir = tmp_path / "data"

    settings = _Settings()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.settings.get_settings", lambda: settings)

    job_id = JobRepository().create(
        job_type="CREATOR_PIPELINE",
        platform="xiaohongshu",
        creator_id="creator-1",
    )

    with TestClient(app) as client:
        response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_type"] == "CREATOR_PIPELINE"
    assert response.json()["status"] == "PENDING"
