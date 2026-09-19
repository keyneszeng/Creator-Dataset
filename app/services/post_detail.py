import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.repositories import (
    ChangeEventRepository,
    MediaRepository,
    PostRepository,
)
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
        change_events: ChangeEventRepository | None = None,
    ) -> None:
        self.gateway = gateway or XiaohongshuGateway()
        self.posts = post_repository or PostRepository()
        self.media = media_repository or MediaRepository()
        self.change_events = change_events or ChangeEventRepository()

    async def _enrich_row(self, row: dict) -> tuple[int, dict[str, bool]]:
        context = row["platform_context"]
        raw = await asyncio.to_thread(
            self.gateway.get_post_detail,
            row["post_id"],
            xsec_token=str(context.get("xsec_token") or ""),
            xsec_source=str(context.get("xsec_source") or "pc_feed"),
        )
        post = normalize_post_detail(raw, row["post_id"])
        changes = self.posts.update_detail(
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
            media=post["media"],
        )

        self.media.reconcile_post_media(
            platform="xiaohongshu",
            post_id=row["post_id"],
            media_items=post["media"],
        )
        return len(post["media"]), changes

    async def enrich_post(self, post_id: str, *, force: bool = False) -> int:
        row = self.posts.get_access_context(
            platform="xiaohongshu",
            post_id=post_id,
        )
        if row is None:
            raise ValueError(f"Unknown post: {post_id}")
        if row.get("has_detail") and not force:
            return 0
        media_registered, _ = await self._enrich_row(row)
        return media_registered

    async def refresh_post(
        self,
        post_id: str,
        *,
        creator_id: str | None = None,
    ) -> dict[str, bool]:
        row = self.posts.get_access_context(
            platform="xiaohongshu",
            post_id=post_id,
        )
        if row is None:
            raise ValueError(f"Unknown post: {post_id}")

        _, changes = await self._enrich_row(row)

        for key in (
            "content_changed",
            "media_changed",
            "engagement_changed",
            "comments_changed",
        ):
            if changes.get(key):
                self.change_events.record(
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    entity_type="post",
                    change_type=key,
                    old_fingerprint=None,
                    new_fingerprint=None,
                    details={"first_detail": changes.get("first_detail", False)},
                )

        return changes

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
            registered, _ = await self._enrich_row(row)
            media_registered += registered
            enriched += 1

        return PostDetailBatchResult(
            creator_id=creator_id,
            requested=len(rows),
            enriched=enriched,
            media_registered=media_registered,
        )
