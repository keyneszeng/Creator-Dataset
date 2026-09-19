import asyncio
from dataclasses import asdict
from app.core.repositories import MediaRepository, OcrRepository
from app.ocr.base import OcrEngine
from app.ocr.factory import create_ocr_engine
from app.storage.materialize import materialize_media


class OcrService:
    def __init__(
        self,
        *,
        media_repository: MediaRepository | None = None,
        ocr_repository: OcrRepository | None = None,
        engine: OcrEngine | None = None,
    ) -> None:
        self.media = media_repository or MediaRepository()
        self.ocr = ocr_repository or OcrRepository()
        self.engine = engine or create_ocr_engine()

    async def process_post_images(
        self,
        post_id: str,
        *,
        include_comment_images: bool = True,
        only_missing: bool = True,
        limit: int = 200,
    ) -> dict[str, int]:
        media_items = self.media.list_local_images(
            post_id=post_id,
            include_comment_images=include_comment_images,
            limit=limit,
        )

        processed = 0
        skipped = 0
        failed = 0

        for item in media_items:
            if only_missing and self.ocr.exists(
                media_id=item["id"],
                engine=self.engine.name,
            ):
                skipped += 1
                continue

            try:
                with materialize_media(item) as local_path:
                    result = await asyncio.to_thread(
                        self.engine.recognize,
                        local_path,
                    )
                self.ocr.save_result(
                    media_id=item["id"],
                    engine=result.engine,
                    engine_version=result.engine_version,
                    language=result.language,
                    full_text=result.full_text,
                    average_confidence=result.average_confidence,
                    blocks=[asdict(block) for block in result.blocks],
                )
                processed += 1
            except Exception as exc:
                failed += 1
                self.ocr.save_error(
                    media_id=item["id"],
                    engine=self.engine.name,
                    error=str(exc),
                )

        return {
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "total_candidates": len(media_items),
        }
