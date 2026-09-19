import asyncio
from dataclasses import asdict
from pathlib import Path

from app.core.repositories import MediaRepository, TranscriptRepository
from app.stt.base import SttEngine
from app.stt.factory import create_stt_engine


class SttService:
    def __init__(
        self,
        *,
        media_repository: MediaRepository | None = None,
        transcript_repository: TranscriptRepository | None = None,
        engine: SttEngine | None = None,
    ) -> None:
        self.media = media_repository or MediaRepository()
        self.transcripts = transcript_repository or TranscriptRepository()
        self.engine = engine or create_stt_engine()

    async def process_post_videos(
        self,
        post_id: str,
        *,
        only_missing: bool = True,
        limit: int = 20,
    ) -> dict[str, int]:
        items = self.media.list_local_videos(
            post_id=post_id,
            limit=limit,
        )

        processed = 0
        skipped = 0
        failed = 0

        for item in items:
            if only_missing and self.transcripts.exists(
                media_id=item["id"],
                engine=self.engine.name,
                model=self.engine.model_name,
            ):
                skipped += 1
                continue

            local_path = Path(item["local_path"])
            if not local_path.exists():
                failed += 1
                self.transcripts.save_error(
                    media_id=item["id"],
                    engine=self.engine.name,
                    model=self.engine.model_name,
                    error=f"Media file not found: {local_path}",
                )
                continue

            try:
                result = await asyncio.to_thread(
                    self.engine.transcribe,
                    local_path,
                )
                self.transcripts.save_result(
                    media_id=item["id"],
                    engine=result.engine,
                    engine_version=result.engine_version,
                    model=result.model,
                    language=result.language,
                    language_probability=result.language_probability,
                    full_text=result.full_text,
                    segments=[asdict(segment) for segment in result.segments],
                )
                processed += 1
            except Exception as exc:
                failed += 1
                self.transcripts.save_error(
                    media_id=item["id"],
                    engine=self.engine.name,
                    model=self.engine.model_name,
                    error=str(exc),
                )

        return {
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "total_candidates": len(items),
        }
