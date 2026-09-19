from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import database
from app.core.repositories import JobRepository
from app.worker import DurableWorker


class FakeCreatorImportService:
    calls = 0

    async def import_creator(self, url: str, *, max_pages: int):
        type(self).calls += 1
        if type(self).calls == 1:
            return SimpleNamespace(
                discovery_finished=False,
                discovered_posts=20,
            )
        return SimpleNamespace(
            discovery_finished=True,
            discovered_posts=35,
        )


@pytest.mark.asyncio
async def test_creator_import_continues_without_being_marked_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "creator-import.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path
        worker_lease_seconds = 30
        worker_heartbeat_seconds = 5
        worker_poll_seconds = 0.01

    settings = _Settings()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.worker.CreatorImportService",
        FakeCreatorImportService,
    )

    FakeCreatorImportService.calls = 0
    jobs = JobRepository()
    job_id = jobs.enqueue(
        job_type="CREATOR_IMPORT",
        creator_id="creator-1",
        payload={
            "url": (
                "https://www.xiaohongshu.com/user/profile/creator-1"
            ),
            "max_pages": 20,
        },
        max_attempts=5,
    )

    worker = DurableWorker(
        worker_id="creator-import-worker",
        jobs=jobs,
    )

    assert await worker.run_once() is True
    first = jobs.get(job_id=job_id)
    assert first["status"] == "RETRY"
    assert first["attempt"] == 1

    assert await worker.run_once() is True
    second = jobs.get(job_id=job_id)
    assert second["status"] == "COMPLETE"
    assert second["attempt"] == 2
    assert FakeCreatorImportService.calls == 2
