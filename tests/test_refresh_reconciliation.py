from pathlib import Path

from app.core import database
from app.core.checkpoints import CheckpointRepository
from app.core.repositories import MediaRepository


def test_comment_checkpoint_reset_removes_root_and_replies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "checkpoint-reset.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    checkpoints = CheckpointRepository()
    checkpoints.save(
        platform="xiaohongshu",
        scope="root_comments",
        object_id="post-1",
        cursor="end",
        finished=True,
    )
    checkpoints.save(
        platform="xiaohongshu",
        scope="sub_comments",
        object_id="post-1:c1",
        cursor="end",
        finished=True,
    )

    removed = checkpoints.reset_comment_crawl(
        platform="xiaohongshu",
        post_id="post-1",
    )

    assert removed == 2
    assert checkpoints.get(
        platform="xiaohongshu",
        scope="root_comments",
        object_id="post-1",
    ) is None


def test_media_reconciliation_deactivates_removed_media(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "media-reconcile.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    media = MediaRepository()
    old_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="image",
        remote_url="https://example.test/old.jpg",
    )

    media.reconcile_post_media(
        platform="xiaohongshu",
        post_id="post-1",
        media_items=[
            {
                "media_type": "image",
                "remote_url": "https://example.test/new.jpg",
            }
        ],
    )

    with database.db_session(db_path) as connection:
        old = connection.execute(
            "SELECT is_active FROM media WHERE id=?",
            (old_id,),
        ).fetchone()
        active = connection.execute(
            "SELECT remote_url FROM media WHERE post_id=? AND is_active=1",
            ("post-1",),
        ).fetchall()

    assert old["is_active"] == 0
    assert [row["remote_url"] for row in active] == [
        "https://example.test/new.jpg"
    ]
