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
        parent_key = f"creator-pipeline:{creator_id}:{run_key}"
        existing = self.jobs.get_by_idempotency_key(
            idempotency_key=parent_key,
        )
        if existing is not None:
            summary = self.jobs.children_summary(
                parent_job_id=int(existing["id"])
            )
            return EnqueueCreatorResult(
                parent_job_id=int(existing["id"]),
                creator_id=creator_id,
                posts_enqueued=summary.get("TOTAL", 0),
            )

        creator_job_id = self.jobs.enqueue(
            job_type="CREATOR_PIPELINE",
            platform="xiaohongshu",
            creator_id=creator_id,
            idempotency_key=parent_key,
            payload={"max_posts": max_posts},
            priority=100,
            max_attempts=1,
        )
        self.jobs.mark_waiting(job_id=creator_job_id)

        for row in rows:
            post_id = str(row["post_id"])
            post_job_id = self.jobs.enqueue(
                job_type="POST_PIPELINE",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=creator_job_id,
                idempotency_key=f"post-pipeline:{creator_job_id}:{post_id}",
                priority=100,
                max_attempts=1,
            )
            self.jobs.mark_waiting(job_id=post_job_id)

            detail_job = self.jobs.enqueue(
                job_type="POST_DETAIL",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=post_job_id,
                idempotency_key=f"stage:{post_job_id}:detail",
                priority=100,
                max_attempts=5,
            )

            terminal_dependencies: list[int] = [detail_job]

            if run_comments:
                comments_job = self.jobs.enqueue(
                    job_type="COMMENTS",
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    parent_job_id=post_job_id,
                    idempotency_key=f"stage:{post_job_id}:comments",
                    priority=110,
                    max_attempts=5,
                    depends_on=[detail_job],
                )
                terminal_dependencies.append(comments_job)

            if run_media:
                media_job = self.jobs.enqueue(
                    job_type="MEDIA_DOWNLOAD",
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    parent_job_id=post_job_id,
                    idempotency_key=f"stage:{post_job_id}:media",
                    priority=110,
                    max_attempts=5,
                    depends_on=[detail_job],
                )
                terminal_dependencies.append(media_job)

                if run_ocr:
                    ocr_job = self.jobs.enqueue(
                        job_type="OCR",
                        platform="xiaohongshu",
                        creator_id=creator_id,
                        post_id=post_id,
                        parent_job_id=post_job_id,
                        idempotency_key=f"stage:{post_job_id}:ocr",
                        priority=120,
                        max_attempts=3,
                        depends_on=[media_job],
                    )
                    terminal_dependencies.append(ocr_job)

                if run_stt:
                    stt_job = self.jobs.enqueue(
                        job_type="STT",
                        platform="xiaohongshu",
                        creator_id=creator_id,
                        post_id=post_id,
                        parent_job_id=post_job_id,
                        idempotency_key=f"stage:{post_job_id}:stt",
                        priority=120,
                        max_attempts=3,
                        depends_on=[media_job],
                    )
                    terminal_dependencies.append(stt_job)

            validation_job = self.jobs.enqueue(
                job_type="VALIDATION",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=post_job_id,
                idempotency_key=f"stage:{post_job_id}:validation",
                priority=130,
                max_attempts=3,
                depends_on=terminal_dependencies,
                payload={
                    "require_comments": run_comments,
                    "require_media": run_media,
                    "require_ocr": run_media and run_ocr,
                    "require_stt": run_media and run_stt,
                },
            )

            if export:
                self.jobs.enqueue(
                    job_type="EXPORT",
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    parent_job_id=post_job_id,
                    idempotency_key=f"stage:{post_job_id}:export",
                    priority=140,
                    max_attempts=3,
                    depends_on=[validation_job],
                )

        return EnqueueCreatorResult(
            parent_job_id=creator_job_id,
            creator_id=creator_id,
            posts_enqueued=len(rows),
        )
