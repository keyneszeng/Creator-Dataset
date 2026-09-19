from dataclasses import dataclass
from uuid import uuid4

from app.core.repositories import JobRepository, PostRepository


@dataclass(frozen=True, slots=True)
class EnqueueCreatorResult:
    parent_job_id: int
    creator_id: str
    posts_enqueued: int


class QueueService:
    def __init__(
        self,
        *,
        jobs: JobRepository | None = None,
        posts: PostRepository | None = None,
    ) -> None:
        self.jobs = jobs or JobRepository()
        self.posts = posts or PostRepository()

    def enqueue_creator_pipeline(
        self,
        creator_id: str,
        *,
        max_posts: int = 100,
        run_comments: bool = True,
        run_media: bool = True,
        run_ocr: bool = True,
        run_stt: bool = True,
        export: bool = True,
        idempotency_key: str | None = None,
    ) -> EnqueueCreatorResult:
        rows = self.posts.list_for_creator(
            platform="xiaohongshu",
            creator_id=creator_id,
            limit=max_posts,
        )
        if not rows:
            raise ValueError(
                f"No discovered posts for creator: {creator_id}. "
                "Import the creator first."
            )

        run_key = idempotency_key or uuid4().hex
        signature = (
            f"comments={int(run_comments)}:"
            f"media={int(run_media)}:"
            f"ocr={int(run_ocr)}:"
            f"stt={int(run_stt)}:"
            f"export={int(export)}"
        )
        parent_job_id = self.jobs.enqueue(
            job_type="CREATOR_PIPELINE",
            platform="xiaohongshu",
            creator_id=creator_id,
            idempotency_key=f"creator-pipeline:{creator_id}:{run_key}",
            payload={
                "max_posts": max_posts,
                "run_comments": run_comments,
                "run_media": run_media,
                "run_ocr": run_ocr,
                "run_stt": run_stt,
                "export": export,
            },
            priority=100,
            max_attempts=1,
        )
        self.jobs.mark_waiting(job_id=parent_job_id)

        for row in rows:
            post_id = str(row["post_id"])
            self.jobs.enqueue(
                job_type="POST_PIPELINE",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=parent_job_id,
                idempotency_key=(
                    f"post-pipeline:{parent_job_id}:{post_id}"
                ),
                payload={
                    "run_comments": run_comments,
                    "run_media": run_media,
                    "run_ocr": run_ocr,
                    "run_stt": run_stt,
                    "export": export,
                },
                priority=100,
                max_attempts=5,
            )

        return EnqueueCreatorResult(
            parent_job_id=parent_job_id,
            creator_id=creator_id,
            posts_enqueued=len(rows),
        )
