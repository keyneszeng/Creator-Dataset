from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.repositories import JobRepository, WorkerRepository
from app.main import app


def test_system_status_reports_queue_and_workers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "system.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path
        data_dir = tmp_path / "data"

    settings = _Settings()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    JobRepository().enqueue(job_type="TEST")
    WorkerRepository().touch(worker_id="worker-test")

    with TestClient(app) as client:
        response = client.get("/api/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["queue"]["PENDING"] == 1
    assert body["workers"]["active"] == 1
    assert body["workers"]["items"][0]["worker_id"] == "worker-test"
