import asyncio
from dataclasses import dataclass

from app.core.repositories import PostRepository
from app.platforms.xiaohongshu.gateway import XiaohongshuGateway
from app.platforms.xiaohongshu.normalizers import normalize_post_detail


@dataclass(frozen=True, slots=True)
class PostDetailBatchResult:
    creator_id: str
    requested: int
    enriched: int


class PostDetailService:
    def __init__(
        self,
        gateway: XiaohongshuGateway | None = None,
        post_repository: PostRepository | None = None,
    ) -> None:
        self.gateway = gateway or XiaohongshuGateway()
        self.posts = post_repository or PostRepository()

    async def enrich_creator(
        self,
        creator_id: str,
        *,
        limit: int = 20,
        only_missing: bool = True,
    ) -> PostDetailBatchResult:
        rows = self.posts.list_for_detail(
            platform="xiaohongshu",
            creator_id=creator_id,
            limit=limit,
            only_missing=only_missing,
        )

        enriched = 0
        for row in rows:
            context = row["platform_context"]
            raw = await asyncio.to_thread(
                self.gateway.get_post_detail,
                row["post_id"],
                xsec_token=str(context.get("xsec_token") or ""),
                xsec_source=str(context.get("xsec_source") or "pc_feed"),
            )
            post = normalize_post_detail(raw, row["post_id"])
            self.posts.update_detail(
                platform="xiaohongshu",
                post_id=row["post_id"],
                title=post["title"],
                content=post["content"],
                post_type=post["post_type"],
                published_at=post["published_at"],
                like_count=post["like_count"],
                favorite_count=post["favorite_count"],
                share_count=post["share_count"],
                reported_comment_count=post["reported_comment_count"],
                raw=raw,
            )
            enriched += 1

        return PostDetailBatchResult(
            creator_id=creator_id,
            requested=len(rows),
            enriched=enriched,
        )
