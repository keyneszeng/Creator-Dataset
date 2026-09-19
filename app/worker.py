import asyncio
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
from app.core.repositories import JobRepository
from app.core.settings import get_settings
from app.services.comment_crawl import CommentCrawlService
from app.services.export import ExportService
from app.services.media_pipeline import MediaPipelineService
from app.services.post_detail import PostDetailService

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]


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
            await CommentCrawlService().crawl_post(post_id)

        if payload.get("run_media", True):
            await MediaPipelineService().process_post(
                post_id,
                run_ocr=bool(payload.get("run_ocr", True)),
                run_stt=bool(payload.get("run_stt", True)),
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
                ok = self.jobs.heartbeat(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
                if not ok:
                    return

    async def run_once(self) -> bool:
        self.jobs.recover_expired_leases()

        job = self.jobs.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return False

        job_id = int(job["id"])
        parent_job_id = job.get("parent_job_id")
        handler = self.handlers.get(str(job["job_type"]))

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

        except (PlatformRequestError, TimeoutError, OSError) as exc:
            self._retry(job, exc)

        except Exception as exc:
            self._retry(job, exc)

        finally:
            stop.set()
            await heartbeat_task
            if parent_job_id:
                self.jobs.reconcile_parent(
                    parent_job_id=int(parent_job_id)
                )

        return True

    def _retry(self, job: dict[str, Any], exc: Exception) -> None:
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
    asyncio.run(DurableWorker().run_forever())


if __name__ == "__main__":
    main()
