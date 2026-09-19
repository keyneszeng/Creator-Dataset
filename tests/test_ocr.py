from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import MediaRepository, OcrRepository
from app.ocr.base import OcrBlock, OcrResult
from app.services.ocr import OcrService


class FakeEngine:
    name = "fake-ocr"

    def recognize(self, image_path: Path) -> OcrResult:
        return OcrResult(
            full_text="第一行\n第二行",
            blocks=[
                OcrBlock(text="第一行", confidence=0.99),
                OcrBlock(text="第二行", confidence=0.95),
            ],
            average_confidence=0.97,
            engine=self.name,
            engine_version="1.0",
            language="ch",
        )


@pytest.mark.asyncio
async def test_ocr_text_is_archived(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "ocr.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"fake-image")

    media = MediaRepository()
    media_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="image",
        remote_url="https://example.test/image.jpg",
        local_path=str(image_path),
        download_status="COMPLETE",
    )

    service = OcrService(
        media_repository=media,
        ocr_repository=OcrRepository(),
        engine=FakeEngine(),
    )
    result = await service.process_post_images("post-1")

    assert result["processed"] == 1

    with database.db_session(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM ocr_results WHERE media_id=?",
            (media_id,),
        ).fetchone()

    assert row["full_text"] == "第一行\n第二行"
    assert row["average_confidence"] == pytest.approx(0.97)
    assert row["status"] == "COMPLETE"
