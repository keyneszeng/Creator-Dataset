import asyncio
from dataclasses import dataclass

from app.core.checkpoints import CheckpointRepository
from app.core.repositories import (
    ChangeEventRepository,
    PostRepository,
    RawSnapshotRepository,
    RefreshRunRepository,
)
from app.platforms.xiaohongshu.gateway import XiaohongshuGateway
from app.platforms.xiaohongshu.normalizers import normalize_posts_page
from app.services.post_detail import PostDetailService
from app.services.queue import QueueService


@dataclass(frozen=True, slots=True)
class IncrementalRefreshResult:
    creator_id: str
    refresh_run_id: int
    pages_scanned: int
    new_posts: int
    changed_posts: int
    unchanged_posts: int
    post_jobs_created: int


class IncrementalRefreshService:
    def __init__(
        self,
        *,
        gateway: XiaohongshuGateway | None = None,
        posts: PostRepository | None = None,
        snapshots: RawSnapshotRepository | None = None,
        changes: ChangeEventRepository | None = None,
        refresh_runs: RefreshRunRepository | None = None,
        detail_service: PostDetailService | None = None,
        queue: QueueService | None = None,
        checkpoints: CheckpointRepository | None = None,
    ) -> None:
        self.gateway = gateway or XiaohongshuGateway()
        self.posts = posts or PostRepository()
        self.snapshots = snapshots or RawSnapshotRepository()
        self.changes = changes or ChangeEventRepository()
        self.refresh_runs = refresh_runs or RefreshRunRepository()
        self.detail_service = detail_service or PostDetailService()
        self.queue = queue or QueueService()
        self.checkpoints = checkpoints or CheckpointRepository()

    async def run(
        self,
        *,
        creator_id: str,
        parent_job_id: int,
        max_pages: int = 3,
        max_recent_posts: int = 30,
        stop_after_unchanged_pages: int = 2,
    ) -> IncrementalRefreshResult:
        refresh_run_id = self.refresh_runs.start(
            platform="xiaohongshu",
            creator_id=creator_id,
            mode="incremental",
        )

        cursor = ""
        pages_scanned = 0
        consecutive_unchanged_pages = 0
        new_posts = 0
        changed_posts = 0
        unchanged_posts = 0
        seen_posts: list[tuple[str, str]] = []

        try:
            while pages_scanned < max_pages:
                raw_page = await asyncio.to_thread(
                    self.gateway.get_creator_posts_page,
                    creator_id,
                    cursor,
                )
                self.snapshots.save(
                    platform="xiaohongshu",
                    resource_type="creator_posts_refresh_page",
                    object_id=creator_id,
                    cursor=cursor or None,
                    payload=raw_page,
                )
                page = normalize_posts_page(raw_page)

                page_has_change = False
                for note in page["notes"]:
                    post_id = note["post_id"]
                    status = self.posts.upsert_discovered(
                        platform="xiaohongshu",
                        creator_id=creator_id,
                        post_id=post_id,
                        source_url=f"https://www.xiaohongshu.com/explore/{post_id}",
                        title=note["title"],
                        post_type=note["post_type"],
                        raw=note["raw"],
                        platform_context={
                            "xsec_token": note["xsec_token"] or "",
                            "xsec_source": note["xsec_source"],
                        },
                    )
                    seen_posts.append((post_id, status))

                    if status == "NEW":
                        new_posts += 1
                        page_has_change = True
                        self.changes.record(
                            platform="xiaohongshu",
                            creator_id=creator_id,
                            post_id=post_id,
                            entity_type="post",
                            change_type="new_post",
                            old_fingerprint=None,
                            new_fingerprint=None,
                            details={"source": "discovery"},
                        )
                    elif status == "CHANGED":
                        changed_posts += 1
                        page_has_change = True
                        self.changes.record(
                            platform="xiaohongshu",
                            creator_id=creator_id,
                            post_id=post_id,
                            entity_type="post",
                            change_type="discovery_changed",
                            old_fingerprint=None,
                            new_fingerprint=None,
                            details={"source": "discovery"},
                        )
                    else:
                        unchanged_posts += 1

                pages_scanned += 1
                if page_has_change:
                    consecutive_unchanged_pages = 0
                else:
                    consecutive_unchanged_pages += 1

                if not page["has_more"]:
                    break
                if consecutive_unchanged_pages >= stop_after_unchanged_pages:
                    break
                if not page["cursor"]:
                    break
                cursor = page["cursor"]

            post_jobs_created = 0
            for post_id, discovery_status in seen_posts[:max_recent_posts]:
                detail_changes = await self.detail_service.refresh_post(
                    post_id,
                    creator_id=creator_id,
                )

                is_new = discovery_status == "NEW" or detail_changes["first_detail"]
                content_or_media = (
                    detail_changes["content_changed"]
                    or detail_changes["media_changed"]
                )
                comments_changed = detail_changes["comments_changed"]
                engagement_changed = detail_changes["engagement_changed"]

                if comments_changed and not is_new:
                    self.checkpoints.reset_comment_crawl(
                        platform="xiaohongshu",
                        post_id=post_id,
                    )

                if is_new:
                    self.queue.enqueue_post_stages(
                        parent_job_id=parent_job_id,
                        creator_id=creator_id,
                        post_id=post_id,
                        run_comments=True,
                        run_media=True,
                        run_ocr=True,
                        run_stt=True,
                        export=True,
                        include_detail=False,
                        key_prefix=f"refresh:{refresh_run_id}",
                    )
                    post_jobs_created += 1
                    continue

                if content_or_media:
                    self.queue.enqueue_post_stages(
                        parent_job_id=parent_job_id,
                        creator_id=creator_id,
                        post_id=post_id,
                        run_comments=comments_changed,
                        run_media=detail_changes["media_changed"],
                        run_ocr=detail_changes["media_changed"],
                        run_stt=detail_changes["media_changed"],
                        export=True,
                        include_detail=False,
                        key_prefix=f"refresh:{refresh_run_id}",
                    )
                    post_jobs_created += 1
                    continue

                if comments_changed:
                    self.queue.enqueue_post_stages(
                        parent_job_id=parent_job_id,
                        creator_id=creator_id,
                        post_id=post_id,
                        run_comments=True,
                        run_media=False,
                        run_ocr=False,
                        run_stt=False,
                        export=True,
                        include_detail=False,
                        key_prefix=f"refresh:{refresh_run_id}",
                    )
                    post_jobs_created += 1
                    continue

                if engagement_changed:
                    self.queue.enqueue_post_stages(
                        parent_job_id=parent_job_id,
                        creator_id=creator_id,
                        post_id=post_id,
                        run_comments=False,
                        run_media=False,
                        run_ocr=False,
                        run_stt=False,
                        export=True,
                        include_detail=False,
                        key_prefix=f"refresh:{refresh_run_id}",
                    )
                    post_jobs_created += 1

            self.refresh_runs.complete(
                refresh_run_id=refresh_run_id,
                new_posts=new_posts,
                changed_posts=changed_posts,
                unchanged_posts=unchanged_posts,
                pages_scanned=pages_scanned,
                status="COMPLETE",
            )

            return IncrementalRefreshResult(
                creator_id=creator_id,
                refresh_run_id=refresh_run_id,
                pages_scanned=pages_scanned,
                new_posts=new_posts,
                changed_posts=changed_posts,
                unchanged_posts=unchanged_posts,
                post_jobs_created=post_jobs_created,
            )

        except Exception:
            self.refresh_runs.complete(
                refresh_run_id=refresh_run_id,
                new_posts=new_posts,
                changed_posts=changed_posts,
                unchanged_posts=unchanged_posts,
                pages_scanned=pages_scanned,
                status="FAILED",
            )
            raise
