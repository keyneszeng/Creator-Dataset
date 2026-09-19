from dataclasses import dataclass

from typing import Any

from app.repositories.factory import create_job_repository, create_post_repository
from app.services.comment_crawl import CommentCrawlService
from app.services.export import ExportService
from app.services.media_pipeline import MediaPipelineService
from app.services.post_detail import PostDetailService


@dataclass(frozen=True, slots=True)
class CreatorPipelineResult:
    creator_id: str
    posts_selected: int
    posts_completed: int
    posts_failed: int
    job_id: int


class CreatorPipelineService:
    def __init__(
        self,
        *,
        posts: Any | None = None,
        jobs: Any | None = None,
        detail_service: PostDetailService | None = None,
        comment_service: CommentCrawlService | None = None,
        media_service: MediaPipelineService | None = None,
        export_service: ExportService | None = None,
    ) -> None:
        self.posts = posts or create_post_repository()
        self.jobs = jobs or create_job_repository()
        self.detail_service = detail_service or PostDetailService()
        self.comment_service = comment_service or CommentCrawlService()
        self.media_service = media_service or MediaPipelineService()
        self.export_service = export_service or ExportService()

    async def run(
        self,
        creator_id: str,
        *,
        max_posts: int = 20,
        run_comments: bool = True,
        run_media: bool = True,
        run_ocr: bool = True,
        run_stt: bool = True,
        export: bool = True,
    ) -> CreatorPipelineResult:
        job_id = self.jobs.create(
            job_type="CREATOR_PIPELINE",
            platform="xiaohongshu",
            creator_id=creator_id,
        )
        self.jobs.mark_running(job_id=job_id)

        selected = self.posts.list_for_creator(
            platform="xiaohongshu",
            creator_id=creator_id,
            limit=max_posts,
        )

        completed = 0
        failed = 0

        try:
            # Enrich missing details in a bounded batch before per-post processing.
            await self.detail_service.enrich_creator(
                creator_id,
                limit=max_posts,
                only_missing=True,
            )

            for item in selected:
                post_id = str(item["post_id"])
                post_job_id = self.jobs.create(
                    job_type="POST_PIPELINE",
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                )
                self.jobs.mark_running(job_id=post_job_id)

                try:
                    if run_comments:
                        await self.comment_service.crawl_post(post_id)

                    if run_media:
                        await self.media_service.process_post(
                            post_id,
                            run_ocr=run_ocr,
                            run_stt=run_stt,
                        )

                    if export:
                        self.export_service.export_post(post_id)

                    self.jobs.mark_complete(job_id=post_job_id)
                    completed += 1
                except Exception as exc:
                    self.jobs.mark_failed(
                        job_id=post_job_id,
                        error=str(exc),
                        status="PARTIAL",
                    )
                    failed += 1

            if failed:
                self.jobs.mark_failed(
                    job_id=job_id,
                    error=f"{failed} post pipeline(s) were partial or failed.",
                    status="PARTIAL",
                )
            else:
                self.jobs.mark_complete(job_id=job_id)

            return CreatorPipelineResult(
                creator_id=creator_id,
                posts_selected=len(selected),
                posts_completed=completed,
                posts_failed=failed,
                job_id=job_id,
            )

        except Exception as exc:
            self.jobs.mark_failed(job_id=job_id, error=str(exc))
            raise
