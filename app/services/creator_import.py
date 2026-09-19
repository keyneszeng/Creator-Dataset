import asyncio
from dataclasses import dataclass

from typing import Any

from app.repositories.factory import (
    create_checkpoint_repository,
    create_creator_repository,
    create_post_repository,
    create_raw_snapshot_repository,
)
from app.platforms.xiaohongshu.gateway import XiaohongshuGateway
from app.platforms.xiaohongshu.normalizers import (
    normalize_creator,
    normalize_posts_page,
)
from app.platforms.xiaohongshu.resolver import resolve_creator_url


@dataclass(frozen=True, slots=True)
class ImportResult:
    creator_id: str
    discovered_posts: int
    discovery_finished: bool
    next_cursor: str


class CreatorImportService:
    def __init__(
        self,
        gateway: XiaohongshuGateway | None = None,
        creator_repository: Any | None = None,
        post_repository: Any | None = None,
        checkpoint_repository: Any | None = None,
        raw_snapshots: Any | None = None,
    ) -> None:
        self.gateway = gateway or XiaohongshuGateway()
        self.creators = creator_repository or create_creator_repository()
        self.posts = post_repository or create_post_repository()
        self.checkpoints = checkpoint_repository or create_checkpoint_repository()
        self.raw_snapshots = raw_snapshots or create_raw_snapshot_repository()

    async def import_creator(
        self, url: str, *, max_pages: int = 20
    ) -> ImportResult:
        resolved = resolve_creator_url(url)
        creator_id = resolved.creator_id

        raw_creator = await asyncio.to_thread(
            self.gateway.get_creator, creator_id
        )
        self.raw_snapshots.save(
            platform="xiaohongshu",
            resource_type="creator_profile",
            object_id=creator_id,
            cursor=None,
            payload=raw_creator,
        )
        creator = normalize_creator(raw_creator, creator_id)
        self.creators.upsert(
            platform="xiaohongshu",
            creator_id=creator_id,
            profile_url=resolved.canonical_url,
            name=creator["name"],
            avatar_url=creator["avatar_url"],
            bio=creator["bio"],
            follower_count=creator["follower_count"],
            following_count=creator["following_count"],
            raw=raw_creator,
        )

        checkpoint = self.checkpoints.get(
            platform="xiaohongshu",
            scope="creator_posts",
            object_id=creator_id,
        )
        cursor = "" if not checkpoint or checkpoint["finished"] else checkpoint["cursor"]
        finished = bool(checkpoint and checkpoint["finished"])

        pages = 0
        while not finished and pages < max_pages:
            raw_page = await asyncio.to_thread(
                self.gateway.get_creator_posts_page,
                creator_id,
                cursor,
            )
            self.raw_snapshots.save(
                platform="xiaohongshu",
                resource_type="creator_posts_page",
                object_id=creator_id,
                cursor=cursor or None,
                payload=raw_page,
            )
            page = normalize_posts_page(raw_page)

            for note in page["notes"]:
                post_id = note["post_id"]
                source_url = (
                    "https://www.xiaohongshu.com/explore/"
                    f"{post_id}"
                )
                self.posts.upsert_discovered(
                    platform="xiaohongshu",
                    creator_id=creator_id,
                    post_id=post_id,
                    source_url=source_url,
                    title=note["title"],
                    post_type=note["post_type"],
                    raw=note["raw"],
                    platform_context={
                        "xsec_token": note["xsec_token"] or "",
                        "xsec_source": note["xsec_source"],
                    },
                )

            cursor = page["cursor"]
            finished = not page["has_more"]
            self.checkpoints.save(
                platform="xiaohongshu",
                scope="creator_posts",
                object_id=creator_id,
                cursor=cursor,
                finished=finished,
                metadata={"pages_processed": pages + 1},
            )
            pages += 1

            if page["has_more"] and not cursor:
                break

        count = self.posts.count_for_creator(
            platform="xiaohongshu",
            creator_id=creator_id,
        )
        self.creators.set_discovered_post_count(
            platform="xiaohongshu",
            creator_id=creator_id,
            count=count,
        )

        return ImportResult(
            creator_id=creator_id,
            discovered_posts=count,
            discovery_finished=finished,
            next_cursor=cursor,
        )
