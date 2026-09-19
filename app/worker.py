import asyncio
import logging
import socket
import uuid
from collections.abc import Awaitable, Callable
from datetime import timezone
from typing import Any

from app.core.errors import (
    AuthenticationRequired,
    IntegrationNotInstalled,
    PlatformBlocked,
    PlatformRequestError,
)
from app.core.jobs import RetryPolicy
from app.core.logging import configure_logging
from app.repositories.factory import create_job_repository, create_worker_repository
from app.jobs.contracts import DurableJobRepository
from app.core.settings import get_settings
from app.services.comment_crawl import CommentCrawlService
from app.services.creator_export import CreatorExportService
from app.services.export import ExportService
from app.services.incremental_refresh import IncrementalRefreshService
from app.services.media import MediaDownloadService
from app.services.ocr import OcrService
from app.services.post_detail import PostDetailService
from app.services.stt import SttService
from app.services.validation import ValidationService

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]

logger = logging.getLogger("creator_dataset.worker")


class DurableWorker:
    def __init__(
        self,
        *,
        worker_id: str | None = None,
        jobs: DurableJobRepository | None = None,
        handlers: dict[str, JobHandler] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        settings = get_settings()
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
        )
        self.jobs = jobs or create_job_repository()
        self.workers = create_worker_repository()
        self.retry_policy = retry_policy or RetryPolicy()
        self.lease_seconds = settings.worker_lease_seconds
        self.heartbeat_seconds = settings.worker_heartbeat_seconds
        self.poll_seconds = settings.worker_poll_seconds
        self.handlers = handlers or {
            "CREATOR_DISCOVERY": self._handle_creator_discovery,
            "CREATOR_EXPORT": self._handle_creator_export,
            "POST_DETAIL": self._handle_post_detail,
            "COMMENTS": self._handle_comments,
            "MEDIA_DOWNLOAD": self._handle_media_download,
            "OCR": self._handle_ocr,
            "STT": self._handle_stt,
            "VALIDATION": self._handle_validation,
            "EXPORT": self._handle_export,
        }

    async def _handle_creator_discovery(self, job: dict[str, Any]) -> None:
        payload = job.get("payload") or {}
        parent_job_id = job.get("parent_job_id")
        if not parent_job_id:
            raise ValueError("Incremental discovery requires a CREATOR_REFRESH parent job.")
        await IncrementalRefreshService().run(
            creator_id=str(job["creator_id"]),
            parent_job_id=int(parent_job_id),
            max_pages=int(payload.get("max_pages") or 3),
            max_recent_posts=int(payload.get("max_recent_posts") or 30),
            stop_after_unchanged_pages=int(
                payload.get("stop_after_unchanged_pages") or 2
            ),
        )

    async def _handle_creator_export(self, job: dict[str, Any]) -> None:
        payload = job.get("payload") or {}
        result = CreatorExportService().export_creator(
            str(job["creator_id"]),
            max_posts=int(payload.get("max_posts") or 10000),
        )
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"Creator export is partial: "
                f"{result['missing_post_exports']} Post export(s) missing."
            )

    async def _handle_post_detail(self, job: dict[str, Any]) -> None:
        await PostDetailService().enrich_post(str(job["post_id"]))

    async def _handle_comments(self, job: dict[str, Any]) -> None:
        result = await CommentCrawlService().crawl_post(str(job["post_id"]))
        if result.status != "COMPLETE":
            raise RuntimeError(
                f"Comment crawl incomplete for {job['post_id']}: "
                f"{result.status}"
            )

    async def _handle_media_download(self, job: dict[str, Any]) -> None:
        result = await MediaDownloadService().download_post_media(
            str(job["post_id"]),
            limit=500,
        )
        if int(result.get("failed") or 0):
            raise RuntimeError(
                f"Media download has {result['failed']} failed item(s)."
            )

    async def _handle_ocr(self, job: dict[str, Any]) -> None:
        result = await OcrService().process_post_images(
            str(job["post_id"]),
            include_comment_images=True,
            only_missing=True,
            limit=2000,
        )
        if int(result.get("failed") or 0):
            raise RuntimeError(
                f"OCR has {result['failed']} failed item(s)."
            )

    async def _handle_stt(self, job: dict[str, Any]) -> None:
        result = await SttService().process_post_videos(
            str(job["post_id"]),
            only_missing=True,
            limit=200,
        )
        if int(result.get("failed") or 0):
            raise RuntimeError(
                f"STT has {result['failed']} failed item(s)."
            )

    async def _handle_validation(self, job: dict[str, Any]) -> None:
        payload = job.get("payload") or {}
        result = ValidationService().validate_post(
            str(job["post_id"]),
            require_comments=bool(payload.get("require_comments", True)),
            require_media=bool(payload.get("require_media", True)),
            require_ocr=bool(payload.get("require_ocr", True)),
            require_stt=bool(payload.get("require_stt", True)),
        )
        if not result.complete:
            raise RuntimeError(
                "Validation failed: " + ", ".join(result.issues)
            )

    async def _handle_export(self, job: dict[str, Any]) -> None:
        ExportService().export_post(str(job["post_id"]))

    async def _heartbeat_loop(
        self,
        *,
        job_id: int,
        stop: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self.heartbeat_seconds,
                )
            except TimeoutError:
                self.workers.touch(
                    worker_id=self.worker_id,
                    current_job_id=job_id,
                )
                ok = self.jobs.heartbeat(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
                if not ok:
                    return

    async def run_once(self) -> bool:
        self.workers.touch(worker_id=self.worker_id)
        recovered = self.jobs.recover_expired_leases()
        dependency_terminal = self.jobs.resolve_failed_dependencies()

        if recovered or dependency_terminal:
            logger.warning(
                "queue recovery performed",
                extra={"worker_id": self.worker_id},
            )

        job = self.jobs.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return False

        job_id = int(job["id"])
        handler = self.handlers.get(str(job["job_type"]))

        self.workers.touch(
            worker_id=self.worker_id,
            current_job_id=job_id,
        )
        logger.info(
            "job claimed",
            extra={
                "worker_id": self.worker_id,
                "job_id": job_id,
                "post_id": job.get("post_id"),
                "creator_id": job.get("creator_id"),
            },
        )

        stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(job_id=job_id, stop=stop)
        )

        try:
            if handler is None:
                raise RuntimeError(
                    f"No worker handler for job type: {job['job_type']}"
                )

            await handler(job)
            self.jobs.mark_complete(job_id=job_id)
            logger.info(
                "job complete",
                extra={
                    "worker_id": self.worker_id,
                    "job_id": job_id,
                    "post_id": job.get("post_id"),
                    "creator_id": job.get("creator_id"),
                },
            )

        except (AuthenticationRequired, PlatformBlocked) as exc:
            self.jobs.mark_failed(
                job_id=job_id,
                error=str(exc),
                status="BLOCKED",
            )

        except IntegrationNotInstalled as exc:
            self.jobs.mark_failed(
                job_id=job_id,
                error=str(exc),
                status="FAILED",
            )

        except ValueError as exc:
            self.jobs.mark_failed(
                job_id=job_id,
                error=str(exc),
                status="FAILED",
            )

        except (PlatformRequestError, TimeoutError, OSError) as exc:
            self._retry(job, exc)

        except Exception as exc:
            self._retry(job, exc)

        finally:
            stop.set()
            await heartbeat_task
            self.workers.clear_job(worker_id=self.worker_id)
            self.jobs.resolve_failed_dependencies()
            self.jobs.reconcile_ancestors(job_id=job_id)

        return True

    def _retry(self, job: dict[str, Any], exc: Exception) -> None:
        logger.warning(
            "job scheduled for retry",
            extra={
                "worker_id": self.worker_id,
                "job_id": int(job["id"]),
                "post_id": job.get("post_id"),
                "creator_id": job.get("creator_id"),
            },
        )
        retry_at = self.retry_policy.next_retry_at(
            int(job.get("attempt") or 1)
        )
        self.jobs.schedule_retry(
            job_id=int(job["id"]),
            error=str(exc),
            next_retry_at=retry_at.astimezone(
                timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def run_forever(self) -> None:
        while True:
            worked = await self.run_once()
            if not worked:
                await asyncio.sleep(self.poll_seconds)


def main() -> None:
    configure_logging()
    asyncio.run(DurableWorker().run_forever())


if __name__ == "__main__":
    main()
