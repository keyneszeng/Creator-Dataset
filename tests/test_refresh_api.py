from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.repositories import (
    ChangeEventRepository,
    RefreshRunRepository,
    RefreshScheduleRepository,
)
from app.main import app


def test_refresh_observability_endpoints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "refresh-api.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path
        data_dir = tmp_path / "data"

    settings = _Settings()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    RefreshScheduleRepository().upsert(
        platform="xiaohongshu",
        creator_id="creator-1",
        interval_minutes=1440,
        max_pages=3,
        max_recent_posts=30,
        stop_after_unchanged_pages=2,
        next_run_at="2099-01-01 00:00:00",
        enabled=True,
    )

    run_id = RefreshRunRepository().start(
        platform="xiaohongshu",
        creator_id="creator-1",
        mode="incremental",
    )
    RefreshRunRepository().complete(
        refresh_run_id=run_id,
        new_posts=1,
        changed_posts=2,
        unchanged_posts=10,
        pages_scanned=2,
    )

    ChangeEventRepository().record(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        entity_type="post",
        change_type="comments_changed",
        old_fingerprint=None,
        new_fingerprint=None,
        details={"reported_comment_count": 10},
    )

    with TestClient(app) as client:
        schedules = client.get("/api/refresh-schedules")
        history = client.get("/api/creators/creator-1/refresh-history")
        changes = client.get("/api/creators/creator-1/changes")
        status = client.get("/api/system/status")

    assert schedules.status_code == 200
    assert schedules.json()["count"] == 1
    assert history.json()["items"][0]["new_posts"] == 1
    assert changes.json()["items"][0]["change_type"] == "comments_changed"
    assert status.json()["refresh_scheduler"]["enabled"] == 1
