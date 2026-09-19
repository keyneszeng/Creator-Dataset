import asyncio
from dataclasses import dataclass

from app.core.checkpoints import CheckpointRepository
from app.core.repositories import AuditRepository, CommentRepository, PostRepository
from app.platforms.xiaohongshu.comments import normalize_comment_page
from app.platforms.xiaohongshu.gateway import XiaohongshuGateway


@dataclass(frozen=True, slots=True)
class CommentCrawlResult:
    post_id: str
    root_comments: int
    reply_comments: int
    failed_threads: int
    status: str
    completeness_ratio: float | None


class CommentCrawlService:
    def __init__(
        self,
        gateway: XiaohongshuGateway | None = None,
        comments: CommentRepository | None = None,
        posts: PostRepository | None = None,
        checkpoints: CheckpointRepository | None = None,
        audits: AuditRepository | None = None,
    ) -> None:
        self.gateway = gateway or XiaohongshuGateway()
        self.comments = comments or CommentRepository()
        self.posts = posts or PostRepository()
        self.checkpoints = checkpoints or CheckpointRepository()
        self.audits = audits or AuditRepository()

    async def crawl_post(
        self,
        post_id: str,
        *,
        max_root_pages: int = 200,
        max_reply_pages: int = 200,
    ) -> CommentCrawlResult:
        post = self.posts.get_access_context(
            platform="xiaohongshu",
            post_id=post_id,
        )
        if post is None:
            raise ValueError(f"Unknown post: {post_id}")

        context = post["platform_context"]
        xsec_token = str(context.get("xsec_token") or "")
        xsec_source = str(context.get("xsec_source") or "pc_feed")

        root_cp = self.checkpoints.get(
            platform="xiaohongshu",
            scope="root_comments",
            object_id=post_id,
        )
        root_cursor = "" if not root_cp or root_cp["finished"] else root_cp["cursor"]
        root_finished = bool(root_cp and root_cp["finished"])

        root_pages = 0
        while not root_finished and root_pages < max_root_pages:
            raw_page = await asyncio.to_thread(
                self.gateway.get_comments_page,
                post_id,
                root_cursor,
                xsec_token,
                xsec_source,
            )
            page = normalize_comment_page(raw_page, post_id=post_id)

            for comment in page["comments"]:
                self.comments.upsert(platform="xiaohongshu", **comment)

            root_cursor = page["cursor"]
            root_finished = not page["has_more"]
            self.checkpoints.save(
                platform="xiaohongshu",
                scope="root_comments",
                object_id=post_id,
                cursor=root_cursor,
                finished=root_finished,
                metadata={"pages_processed": root_pages + 1},
            )
            root_pages += 1
            if page["has_more"] and not root_cursor:
                break

        failed_threads = 0
        roots = self.comments.list_roots_with_replies(
            platform="xiaohongshu",
            post_id=post_id,
        )

        for root in roots:
            root_id = root["comment_id"]
            reply_cp = self.checkpoints.get(
                platform="xiaohongshu",
                scope="sub_comments",
                object_id=f"{post_id}:{root_id}",
            )
            if reply_cp and reply_cp["finished"]:
                continue

            cursor = reply_cp["cursor"] if reply_cp else ""
            finished = False
            pages = 0
            try:
                while not finished and pages < max_reply_pages:
                    raw_page = await asyncio.to_thread(
                        self.gateway.get_sub_comments_page,
                        post_id,
                        root_id,
                        cursor,
                    )
                    page = normalize_comment_page(
                        raw_page,
                        post_id=post_id,
                        root_comment_id=root_id,
                    )
                    for comment in page["comments"]:
                        self.comments.upsert(
                            platform="xiaohongshu",
                            **comment,
                        )

                    cursor = page["cursor"]
                    finished = not page["has_more"]
                    self.checkpoints.save(
                        platform="xiaohongshu",
                        scope="sub_comments",
                        object_id=f"{post_id}:{root_id}",
                        cursor=cursor,
                        finished=finished,
                        metadata={"pages_processed": pages + 1},
                    )
                    pages += 1
                    if page["has_more"] and not cursor:
                        break
            except Exception:
                failed_threads += 1
                continue

        counts = self.comments.counts_for_post(
            platform="xiaohongshu",
            post_id=post_id,
        )
        reply_threads_total = len(roots)
        reply_threads_finished = self.checkpoints.count_finished_prefix(
            platform="xiaohongshu",
            scope="sub_comments",
            object_id_prefix=f"{post_id}:",
        )

        expected = post["reported_comment_count"]
        actual = counts["total"]
        ratio = None
        if expected and expected > 0:
            ratio = min(actual / expected, 1.0)

        pagination_finished = (
            root_finished
            and reply_threads_finished >= reply_threads_total
            and failed_threads == 0
        )
        status = "COMPLETE" if pagination_finished else "PARTIAL"

        self.posts.update_comment_progress(
            platform="xiaohongshu",
            post_id=post_id,
            downloaded_comment_count=actual,
            comment_status=status,
        )
        self.audits.save(
            post_id=post_id,
            expected_comments=expected,
            actual_comments=actual,
            root_comments=counts["root"],
            reply_comments=counts["reply"],
            failed_threads=failed_threads,
            root_pagination_finished=root_finished,
            reply_threads_total=reply_threads_total,
            reply_threads_finished=reply_threads_finished,
            pagination_finished=pagination_finished,
            completeness_ratio=ratio,
            status=status,
        )

        return CommentCrawlResult(
            post_id=post_id,
            root_comments=counts["root"],
            reply_comments=counts["reply"],
            failed_threads=failed_threads,
            status=status,
            completeness_ratio=ratio,
        )
