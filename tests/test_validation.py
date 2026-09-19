from pathlib import Path

from app.core import database
from app.core.repositories import PostRepository
from app.services.validation import ValidationService


def test_validation_reports_missing_comment_completion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "validation.sqlite3"
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
        title="Post",
        post_type="normal",
        raw={},
        platform_context={},
    )
    posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Post",
        content="Body",
        post_type="normal",
        published_at=1,
        like_count=1,
        favorite_count=1,
        share_count=1,
        reported_comment_count=1,
        raw={},
    )

    result = ValidationService().validate_post(
        "post-1",
        require_comments=True,
        require_media=False,
        require_ocr=False,
        require_stt=False,
    )

    assert result.complete is False
    assert "comments_missing" in result.issues
