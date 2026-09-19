from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import MediaRepository, TranscriptRepository
from app.services.stt import SttService
from app.stt.base import TranscriptResult, TranscriptSegment


class FakeSttEngine:
    name = "fake-stt"
    model_name = "fake-model"

    def transcribe(self, media_path: Path) -> TranscriptResult:
        return TranscriptResult(
            full_text="第一句\n第二句",
            segments=[
                TranscriptSegment(start=0.0, end=1.2, text="第一句"),
                TranscriptSegment(start=1.2, end=2.8, text="第二句"),
            ],
            engine=self.name,
            engine_version="1.0",
            model=self.model_name,
            language="zh",
            language_probability=0.99,
        )


@pytest.mark.asyncio
async def test_video_transcript_is_archived(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "stt.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake-video")

    media = MediaRepository()
    media_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="video",
        remote_url="https://example.test/video.mp4",
        local_path=str(video_path),
        download_status="COMPLETE",
    )

    service = SttService(
        media_repository=media,
        transcript_repository=TranscriptRepository(),
        engine=FakeSttEngine(),
    )
    result = await service.process_post_videos("post-1")

    assert result["processed"] == 1

    with database.db_session(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM transcripts WHERE media_id=?",
            (media_id,),
        ).fetchone()

    assert row["full_text"] == "第一句\n第二句"
    assert row["language"] == "zh"
    assert row["status"] == "COMPLETE"
