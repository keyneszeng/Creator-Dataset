from pathlib import Path

from app.core import database
from app.core.repositories import (
    CommentRepository,
    ExportRepository,
    MediaRepository,
    OcrRepository,
    PostRepository,
    TextUnitRepository,
)
from app.services.analysis_corpus import AnalysisCorpusService


def test_rebuild_post_creates_provenance_units(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "corpus.sqlite3"
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
        title="Title",
        post_type="normal",
        raw={},
        platform_context={},
    )
    posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="作者正文",
        post_type="normal",
        published_at=1,
        like_count=1,
        favorite_count=1,
        share_count=1,
        reported_comment_count=1,
        raw={},
    )

    CommentRepository().upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id="c1",
        root_comment_id="c1",
        parent_comment_id=None,
        user_id="u1",
        user_name="Alice",
        user_avatar=None,
        content="评论正文",
        like_count=1,
        ip_location=None,
        published_at=1,
        depth=0,
        has_more_replies=False,
        reply_count=0,
        pictures=[],
        picture_urls=[],
        raw={},
    )

    media = MediaRepository()
    media_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="image",
        remote_url="https://example.test/a.jpg",
        local_path="/tmp/a.jpg",
        download_status="COMPLETE",
    )
    OcrRepository().save_result(
        media_id=media_id,
        engine="fake",
        engine_version="1",
        language="ch",
        full_text="图片文字",
        average_confidence=0.98,
        blocks=[],
    )

    service = AnalysisCorpusService(
        export_repository=ExportRepository(),
        text_units=TextUnitRepository(),
    )
    result = service.rebuild_post("post-1")

    assert result["text_units"] == 3

    units = TextUnitRepository().list_for_post(post_id="post-1")
    assert {unit["unit_type"] for unit in units} == {
        "author_text",
        "image_ocr",
        "comment",
    }
