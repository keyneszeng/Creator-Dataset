from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import RefreshScheduleRepository
from app.scheduler import RefreshScheduler


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def enqueue_creator_refresh(self, creator_id: str, **kwargs):
        self.calls.append({"creator_id": creator_id, **kwargs})
        return 123


@pytest.mark.asyncio
async def test_scheduler_enqueues_due_refresh(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "scheduler.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    schedules = RefreshScheduleRepository()
    schedule_id = schedules.upsert(
        platform="xiaohongshu",
        creator_id="creator-1",
        interval_minutes=60,
        max_pages=3,
        max_recent_posts=30,
        stop_after_unchanged_pages=2,
        next_run_at="2000-01-01 00:00:00",
        enabled=True,
    )

    queue = FakeQueue()
    scheduler = RefreshScheduler(
        schedules=schedules,
        queue=queue,
        poll_seconds=0.01,
    )

    assert await scheduler.run_once() == 1
    assert queue.calls[0]["creator_id"] == "creator-1"
    assert queue.calls[0]["idempotency_key"].startswith(
        f"schedule:{schedule_id}:"
    )

    schedule = schedules.list_all()[0]
    assert schedule["last_run_at"] is not None
    assert schedule["next_run_at"] > schedule["last_run_at"]
