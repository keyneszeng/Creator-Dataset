from pathlib import Path

from app.core import database
from app.core.repositories import RawSnapshotRepository


def test_raw_snapshot_is_content_deduplicated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "raw.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    repository = RawSnapshotRepository()
    payload = {"cursor": "next", "items": [{"id": "a"}]}

    first = repository.save(
        platform="xiaohongshu",
        resource_type="root_comments_page",
        object_id="post-1",
        cursor="cursor-1",
        payload=payload,
    )
    second = repository.save(
        platform="xiaohongshu",
        resource_type="root_comments_page",
        object_id="post-1",
        cursor="cursor-1",
        payload=payload,
    )

    assert first == second

    snapshots = repository.list_for_object(
        platform="xiaohongshu",
        resource_type="root_comments_page",
        object_id="post-1",
    )
    assert len(snapshots) == 1
    assert snapshots[0]["payload"] == payload
