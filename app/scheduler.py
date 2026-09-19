import asyncio
import logging

from app.core.logging import configure_logging
from typing import Any

from app.repositories.factory import create_refresh_schedule_repository
from app.services.queue import QueueService

logger = logging.getLogger("creator_dataset.scheduler")


class RefreshScheduler:
    def __init__(
        self,
        *,
        schedules: Any | None = None,
        queue: QueueService | None = None,
        poll_seconds: float = 30.0,
    ) -> None:
        self.schedules = schedules or create_refresh_schedule_repository()
        self.queue = queue or QueueService()
        self.poll_seconds = poll_seconds

    async def run_once(self) -> int:
        due = self.schedules.due(limit=100)
        enqueued = 0

        for schedule in due:
            schedule_id = int(schedule["id"])
            creator_id = str(schedule["creator_id"])
            next_run_at = str(schedule["next_run_at"])

            try:
                self.queue.enqueue_creator_refresh(
                    creator_id,
                    max_pages=int(schedule["max_pages"]),
                    max_recent_posts=int(schedule["max_recent_posts"]),
                    stop_after_unchanged_pages=int(
                        schedule["stop_after_unchanged_pages"]
                    ),
                    idempotency_key=(
                        f"schedule:{schedule_id}:{next_run_at}"
                    ),
                )
                self.schedules.mark_enqueued(
                    schedule_id=schedule_id,
                    interval_minutes=int(schedule["interval_minutes"]),
                )
                enqueued += 1
                logger.info(
                    "scheduled creator refresh enqueued",
                    extra={"creator_id": creator_id},
                )
            except Exception:
                logger.exception(
                    "failed to enqueue scheduled creator refresh",
                    extra={"creator_id": creator_id},
                )

        return enqueued

    async def run_forever(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self.poll_seconds)


def main() -> None:
    configure_logging()
    asyncio.run(RefreshScheduler().run_forever())


if __name__ == "__main__":
    main()
