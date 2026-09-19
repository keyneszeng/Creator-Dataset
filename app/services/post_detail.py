import asyncio
from dataclasses import dataclass

from app.core.repositories import MediaRepository, PostRepository
from app.platforms.xiaohongshu.gateway import XiaohongshuGateway
from app.platforms.xiaohongshu.normalizers import normalize_post_detail


@dataclass(frozen=True, slots=True)
class PostDetailBatchResult:
    creator_id: str
    requested: int
    enriched: int
    media_registered: int


class PostDetailService:
    def __init__(
        self,
        gateway: XiaohongshuGateway | None = None,
        post_repository: PostRepository | None = None,
        media_repository: MediaRepository | None = None,
    ) -> None:
        self.gateway = gateway or XiaohongshuGateway()
        self.posts = post_repository or PostRepository()
        self.media = media_repository or MediaRepository()

    async def _enrich_row(self, row: dict) -> int:
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

        media_registered = 0
        for media in post["media"]:
            self.media.upsert(
                platform="xiaohongshu",
                post_id=row["post_id"],
                comment_id=None,
                media_type=media["media_type"],
                remote_url=media["remote_url"],
            )
            media_registered += 1
        return media_registered

    async def enrich_post(self, post_id: str, *, force: bool = False) -> int:
        row = self.posts.get_access_context(
            platform="xiaohongshu",
            post_id=post_id,
        )
        if row is None:
            raise ValueError(f"Unknown post: {post_id}")
        if row.get("has_detail") and not force:
            return 0
        return await self._enrich_row(row)

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
        media_registered = 0

        for row in rows:
            media_registered += await self._enrich_row(row)
            enriched += 1

        return PostDetailBatchResult(
            creator_id=creator_id,
            requested=len(rows),
            enriched=enriched,
            media_registered=media_registered,
        )
