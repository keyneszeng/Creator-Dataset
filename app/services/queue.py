from dataclasses import dataclass
from uuid import uuid4

from app.core.repositories import JobRepository, PostRepository
from app.jobs.contracts import DurableJobRepository


@dataclass(frozen=True, slots=True)
class EnqueueCreatorResult:
    parent_job_id: int
    creator_id: str
    posts_enqueued: int


class QueueService:
    def __init__(
        self,
        *,
        jobs: DurableJobRepository | None = None,
        posts: PostRepository | None = None,
    ) -> None:
        self.jobs = jobs or JobRepository()
        self.posts = posts or PostRepository()

    def enqueue_post_stages(
        self,
        *,
        parent_job_id: int,
        creator_id: str,
        post_id: str,
        run_comments: bool,
        run_media: bool,
        run_ocr: bool,
        run_stt: bool,
        export: bool,
        include_detail: bool = True,
        key_prefix: str = "stage",
    ) -> int:
        post_job_id = self.jobs.enqueue(
            job_type="POST_PIPELINE",
            platform="xiaohongshu",
            creator_id=creator_id,
            post_id=post_id,
            parent_job_id=parent_job_id,
            idempotency_key=f"{key_prefix}:post:{parent_job_id}:{post_id}",
            priority=100,
            max_attempts=1,
        )
        self.jobs.mark_waiting(job_id=post_job_id)

        dependencies: list[int] = []
        detail_job: int | None = None
        if include_detail:
            detail_job = self.jobs.enqueue(
                job_type="POST_DETAIL",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=post_job_id,
                idempotency_key=f"{key_prefix}:{post_job_id}:detail",
                priority=100,
                max_attempts=5,
            )
            dependencies.append(detail_job)

        if run_comments:
            comments_job = self.jobs.enqueue(
                job_type="COMMENTS",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=post_job_id,
                idempotency_key=f"{key_prefix}:{post_job_id}:comments",
                priority=110,
                max_attempts=5,
                depends_on=[detail_job] if detail_job else [],
            )
            dependencies.append(comments_job)

        media_job: int | None = None
        if run_media:
            media_job = self.jobs.enqueue(
                job_type="MEDIA_DOWNLOAD",
                platform="xiaohongshu",
                creator_id=creator_id,
                post_id=post_id,
                parent_job_id=post_job_id,
                idempotency_key=f"{key_prefix}:{post_job_id}:media",
                priority=110,
                max_attempts=5,
                depends_on=[detail_job] if detail_job else [],
            )
            dependencies.append(media_job)

            if run_ocr:
                ocr_job = self.jobs.enqueue(
                    job_type="OCR",
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    parent_job_id=post_job_id,
                    idempotency_key=f"{key_prefix}:{post_job_id}:ocr",
                    priority=120,
                    max_attempts=3,
                    depends_on=[media_job],
                )
                dependencies.append(ocr_job)

            if run_stt:
                stt_job = self.jobs.enqueue(
                    job_type="STT",
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    parent_job_id=post_job_id,
                    idempotency_key=f"{key_prefix}:{post_job_id}:stt",
                    priority=120,
                    max_attempts=3,
                    depends_on=[media_job],
                )
                dependencies.append(stt_job)

        validation_job = self.jobs.enqueue(
            job_type="VALIDATION",
            platform="xiaohongshu",
            creator_id=creator_id,
            post_id=post_id,
            parent_job_id=post_job_id,
            idempotency_key=f"{key_prefix}:{post_job_id}:validation",
            priority=130,
            max_attempts=3,
            depends_on=dependencies,
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
                idempotency_key=f"{key_prefix}:{post_job_id}:export",
                priority=140,
                max_attempts=3,
                depends_on=[validation_job],
            )
        return post_job_id

    def enqueue_creator_refresh(
        self,
        creator_id: str,
        *,
        max_pages: int = 3,
        max_recent_posts: int = 30,
        stop_after_unchanged_pages: int = 2,
        idempotency_key: str | None = None,
    ) -> int:
        run_key = idempotency_key or uuid4().hex
        parent_key = f"creator-refresh:{creator_id}:{run_key}"
        existing = self.jobs.get_by_idempotency_key(
            idempotency_key=parent_key,
        )
        if existing:
            return int(existing["id"])

        parent_job_id = self.jobs.enqueue(
            job_type="CREATOR_REFRESH",
            platform="xiaohongshu",
            creator_id=creator_id,
            idempotency_key=parent_key,
            priority=80,
            max_attempts=1,
        )
        self.jobs.mark_waiting(job_id=parent_job_id)
        self.jobs.enqueue(
            job_type="CREATOR_DISCOVERY",
            platform="xiaohongshu",
            creator_id=creator_id,
            parent_job_id=parent_job_id,
            idempotency_key=f"refresh-discovery:{parent_job_id}",
            payload={
                "refresh": True,
                "max_pages": max_pages,
                "max_recent_posts": max_recent_posts,
                "stop_after_unchanged_pages": stop_after_unchanged_pages,
            },
            priority=80,
            max_attempts=5,
        )
        return parent_job_id

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
            self.enqueue_post_stages(
                parent_job_id=creator_job_id,
                creator_id=creator_id,
                post_id=str(row["post_id"]),
                run_comments=run_comments,
                run_media=run_media,
                run_ocr=run_ocr,
                run_stt=run_stt,
                export=export,
                include_detail=True,
                key_prefix="stage",
            )

        return EnqueueCreatorResult(
            parent_job_id=creator_job_id,
            creator_id=creator_id,
            posts_enqueued=len(rows),
        )
