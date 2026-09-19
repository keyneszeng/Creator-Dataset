from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import JobRepository, PostRepository
from app.services.creator_pipeline import CreatorPipelineService


class FakeDetailService:
    async def enrich_creator(self, creator_id: str, *, limit: int, only_missing: bool):
        return object()


class FakeCommentService:
    def __init__(self) -> None:
        self.posts: list[str] = []

    async def crawl_post(self, post_id: str):
        self.posts.append(post_id)
        return object()


class FakeMediaService:
    def __init__(self) -> None:
        self.posts: list[str] = []

    async def process_post(self, post_id: str, *, run_ocr: bool, run_stt: bool):
        self.posts.append(post_id)
        return {}


class FakeExportService:
    def __init__(self) -> None:
        self.posts: list[str] = []

    def export_post(self, post_id: str):
        self.posts.append(post_id)
        return {}


@pytest.mark.asyncio
async def test_creator_pipeline_runs_all_selected_posts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "pipeline.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    posts = PostRepository()
    for index in range(2):
        posts.upsert_discovered(
            platform="xiaohongshu",
            creator_id="creator-1",
            post_id=f"post-{index}",
            source_url=f"https://www.xiaohongshu.com/explore/post-{index}",
            title=f"Post {index}",
            post_type="normal",
            raw={},
            platform_context={},
        )

    comments = FakeCommentService()
    media = FakeMediaService()
    export = FakeExportService()

    service = CreatorPipelineService(
        posts=posts,
        jobs=JobRepository(),
        detail_service=FakeDetailService(),
        comment_service=comments,
        media_service=media,
        export_service=export,
    )

    result = await service.run(
        "creator-1",
        max_posts=2,
        run_comments=True,
        run_media=True,
        run_ocr=True,
        run_stt=True,
        export=True,
    )

    assert result.posts_completed == 2
    assert result.posts_failed == 0
    assert comments.posts == ["post-0", "post-1"]
    assert media.posts == ["post-0", "post-1"]
    assert export.posts == ["post-0", "post-1"]

    job = JobRepository().get(job_id=result.job_id)
    assert job["status"] == "COMPLETE"
