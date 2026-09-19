from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import (
    ChangeEventRepository,
    PostRepository,
    RawSnapshotRepository,
    RefreshRunRepository,
)
from app.services.incremental_refresh import IncrementalRefreshService


class FakeGateway:
    def get_creator_posts_page(self, creator_id: str, cursor: str = ""):
        return {
            "notes": [
                {
                    "note_id": "post-1",
                    "display_title": "Updated",
                    "type": "normal",
                    "xsec_token": "token",
                }
            ],
            "cursor": "",
            "has_more": False,
        }


class FakeDetailService:
    def __init__(self, changes: dict[str, bool]) -> None:
        self.changes = changes

    async def refresh_post(self, post_id: str, *, creator_id: str | None = None):
        return self.changes


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def enqueue_post_stages(self, **kwargs):
        self.calls.append(kwargs)
        return 1


@pytest.mark.asyncio
async def test_comments_change_only_enqueues_comments_and_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "refresh.sqlite3"
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
        title="Updated",
        post_type="normal",
        raw={
            "note_id": "post-1",
            "display_title": "Updated",
            "type": "normal",
            "xsec_token": "token",
        },
        platform_context={"xsec_token": "token", "xsec_source": "pc_feed"},
    )

    queue = FakeQueue()
    service = IncrementalRefreshService(
        gateway=FakeGateway(),
        posts=posts,
        snapshots=RawSnapshotRepository(),
        changes=ChangeEventRepository(),
        refresh_runs=RefreshRunRepository(),
        detail_service=FakeDetailService({
            "first_detail": False,
            "content_changed": False,
            "media_changed": False,
            "engagement_changed": False,
            "comments_changed": True,
            "any_changed": True,
        }),
        queue=queue,
    )

    result = await service.run(
        creator_id="creator-1",
        parent_job_id=99,
        max_pages=1,
        max_recent_posts=1,
    )

    assert result.post_jobs_created == 1
    assert len(queue.calls) == 1
    call = queue.calls[0]
    assert call["run_comments"] is True
    assert call["run_media"] is False
    assert call["run_ocr"] is False
    assert call["run_stt"] is False
    assert call["export"] is True


@pytest.mark.asyncio
async def test_engagement_change_only_enqueues_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "refresh-engagement.sqlite3"
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
        title="Updated",
        post_type="normal",
        raw={
            "note_id": "post-1",
            "display_title": "Updated",
            "type": "normal",
            "xsec_token": "token",
        },
        platform_context={"xsec_token": "token", "xsec_source": "pc_feed"},
    )

    queue = FakeQueue()
    service = IncrementalRefreshService(
        gateway=FakeGateway(),
        posts=posts,
        snapshots=RawSnapshotRepository(),
        changes=ChangeEventRepository(),
        refresh_runs=RefreshRunRepository(),
        detail_service=FakeDetailService({
            "first_detail": False,
            "content_changed": False,
            "media_changed": False,
            "engagement_changed": True,
            "comments_changed": False,
            "any_changed": True,
        }),
        queue=queue,
    )

    await service.run(
        creator_id="creator-1",
        parent_job_id=100,
        max_pages=1,
        max_recent_posts=1,
    )

    call = queue.calls[0]
    assert call["run_comments"] is False
    assert call["run_media"] is False
    assert call["export"] is True
