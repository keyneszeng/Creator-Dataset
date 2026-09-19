from pathlib import Path

from app.core import database
from app.core.repositories import ExportRepository, MediaRepository, OcrRepository, PostRepository
from app.services.export import ExportService


def test_export_includes_ocr_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "export.sqlite3"
    data_dir = tmp_path / "data"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

        def __init__(self) -> None:
            self.data_dir = tmp_path / "data"

    settings = _Settings()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.services.export.get_settings", lambda: settings)

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://www.xiaohongshu.com/explore/post-1",
        title="Title",
        post_type="normal",
        raw={},
        platform_context={},
    )
    posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="Author body",
        post_type="normal",
        published_at=1,
        like_count=1,
        favorite_count=1,
        share_count=1,
        reported_comment_count=0,
        raw={},
    )

    media = MediaRepository()
    media_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="image",
        remote_url="https://example.test/image.jpg",
        local_path="/tmp/image.jpg",
        download_status="COMPLETE",
    )
    OcrRepository().save_result(
        media_id=media_id,
        engine="fake",
        engine_version="1",
        language="ch",
        full_text="图片里的知识",
        average_confidence=0.99,
        blocks=[],
    )

    result = ExportService(ExportRepository()).export_post("post-1")

    markdown = Path(result["knowledge_markdown"]).read_text(encoding="utf-8")
    assert "Author body" in markdown
    assert "图片里的知识" in markdown
    assert f"Media {media_id}" in markdown
