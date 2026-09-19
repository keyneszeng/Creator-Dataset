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
from app.core.repositories import JobRepository, WorkerRepository
from app.core.settings import get_settings
from app.services.comment_crawl import CommentCrawlService
from app.services.export import ExportService
from app.services.media_pipeline import MediaPipelineService
from app.services.post_detail import PostDetailService

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]

logger = logging.getLogger("creator_dataset.worker")


class DurableWorker:
    def __init__(
        self,
        *,
        worker_id: str | None = None,
        jobs: JobRepository | None = None,
        handlers: dict[str, JobHandler] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        settings = get_settings()
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
        )
        self.jobs = jobs or JobRepository()
        self.workers = WorkerRepository()
        self.retry_policy = retry_policy or RetryPolicy()
        self.lease_seconds = settings.worker_lease_seconds
        self.heartbeat_seconds = settings.worker_heartbeat_seconds
        self.poll_seconds = settings.worker_poll_seconds
        self.handlers = handlers or {
            "POST_PIPELINE": self._handle_post_pipeline,
        }

    async def _handle_post_pipeline(self, job: dict[str, Any]) -> None:
        post_id = str(job["post_id"])
        payload = job.get("payload") or {}

        await PostDetailService().enrich_post(post_id)

        if payload.get("run_comments", True):
            comment_result = await CommentCrawlService().crawl_post(post_id)
            if comment_result.status != "COMPLETE":
                raise RuntimeError(
                    f"Comment crawl incomplete for {post_id}: "
                    f"{comment_result.status}"
                )

        if payload.get("run_media", True):
            media_result = await MediaPipelineService().process_post(
                post_id,
                run_ocr=bool(payload.get("run_ocr", True)),
                run_stt=bool(payload.get("run_stt", True)),
            )
            download = media_result.get("download") or {}
            ocr = media_result.get("ocr") or {}
            stt = media_result.get("stt") or {}
            failed = (
                int(download.get("failed") or 0)
                + int(ocr.get("failed") or 0)
                + int(stt.get("failed") or 0)
            )
            if failed:
                raise RuntimeError(
                    f"Media pipeline has {failed} failed item(s) for {post_id}."
                )

        if payload.get("export", True):
            ExportService().export_post(post_id)

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
        if recovered:
            logger.warning(
                "recovered expired job leases",
                extra={"worker_id": self.worker_id},
            )

        job = self.jobs.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return False

        job_id = int(job["id"])
        parent_job_id = job.get("parent_job_id")
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
            logger.warning(
                "job blocked",
                extra={"worker_id": self.worker_id, "job_id": job_id},
            )
            self.jobs.mark_failed(
                job_id=job_id,
                error=str(exc),
                status="BLOCKED",
            )

        except IntegrationNotInstalled as exc:
            logger.error(
                "job integration missing",
                extra={"worker_id": self.worker_id, "job_id": job_id},
            )
            self.jobs.mark_failed(
                job_id=job_id,
                error=str(exc),
                status="FAILED",
            )

        except ValueError as exc:
            logger.error(
                "job failed permanently",
                extra={"worker_id": self.worker_id, "job_id": job_id},
            )
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
            if parent_job_id:
                self.jobs.reconcile_parent(
                    parent_job_id=int(parent_job_id)
                )

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
