from pathlib import Path

from app.core import database
from app.core.repositories import (
    ExportRepository,
    MediaRepository,
    PostRepository,
    TextUnitRepository,
    TranscriptRepository,
)
from app.services.analysis_corpus import AnalysisCorpusService


def test_transcript_enters_analysis_corpus(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "transcript-corpus.sqlite3"
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
        post_type="video",
        raw={},
        platform_context={},
    )
    posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="正文",
        post_type="video",
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
        media_type="video",
        remote_url="https://example.test/video.mp4",
        local_path="/tmp/video.mp4",
        download_status="COMPLETE",
    )
    TranscriptRepository().save_result(
        media_id=media_id,
        engine="fake-stt",
        engine_version="1",
        model="fake-model",
        language="zh",
        language_probability=0.99,
        full_text="视频里说的话",
        segments=[
            {
                "start": 0.0,
                "end": 2.0,
                "text": "视频里说的话",
                "average_logprob": -0.1,
            }
        ],
    )

    result = AnalysisCorpusService(
        export_repository=ExportRepository(),
        text_units=TextUnitRepository(),
    ).rebuild_post("post-1")

    assert result["text_units"] == 2

    units = TextUnitRepository().list_for_post(post_id="post-1")
    transcript = next(
        unit for unit in units
        if unit["unit_type"] == "video_transcript"
    )
    assert transcript["text"] == "视频里说的话"
    assert transcript["provenance"] == "stt"
