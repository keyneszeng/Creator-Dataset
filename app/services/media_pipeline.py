from app.services.media import MediaDownloadService
from app.services.ocr import OcrService
from app.services.stt import SttService


class MediaPipelineService:
    def __init__(
        self,
        *,
        downloader: MediaDownloadService | None = None,
        ocr_service: OcrService | None = None,
        stt_service: SttService | None = None,
    ) -> None:
        self.downloader = downloader or MediaDownloadService()
        self.ocr_service = ocr_service
        self.stt_service = stt_service

    async def process_post(
        self,
        post_id: str,
        *,
        download_limit: int = 200,
        run_ocr: bool = True,
        ocr_limit: int = 500,
        run_stt: bool = True,
        stt_limit: int = 20,
    ) -> dict[str, object]:
        download = await self.downloader.download_post_media(
            post_id,
            limit=download_limit,
        )

        result: dict[str, object] = {"download": download}

        if run_ocr:
            ocr = self.ocr_service or OcrService()
            result["ocr"] = await ocr.process_post_images(
                post_id,
                include_comment_images=True,
                only_missing=True,
                limit=ocr_limit,
            )

        if run_stt:
            stt = self.stt_service or SttService()
            result["stt"] = await stt.process_post_videos(
                post_id,
                only_missing=True,
                limit=stt_limit,
            )

        return result
