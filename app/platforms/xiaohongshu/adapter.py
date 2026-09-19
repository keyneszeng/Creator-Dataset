from collections.abc import AsyncIterator
from typing import Any

from app.platforms.xiaohongshu.resolver import resolve_creator_url


class XiaohongshuAdapter:
    platform = "xiaohongshu"

    async def resolve_creator(self, url: str) -> dict[str, Any]:
        return resolve_creator_url(url).as_dict()

    async def get_creator(self, creator_id: str) -> dict[str, Any]:
        raise NotImplementedError("Platform client integration is Milestone 1.")

    async def iter_posts(self, creator_id: str) -> AsyncIterator[dict[str, Any]]:
        if False:
            yield {}
        raise NotImplementedError("Post discovery is Milestone 2.")

    async def get_post(self, post_id: str) -> dict[str, Any]:
        raise NotImplementedError("Post detail is Milestone 3.")

    async def iter_root_comments(
        self, post_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        if False:
            yield {}
        raise NotImplementedError("Root comments are Milestone 5.")

    async def iter_replies(
        self, post_id: str, root_comment_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        if False:
            yield {}
        raise NotImplementedError("Replies are Milestone 6.")

    async def download_media(self, url: str, target_path: str) -> None:
        raise NotImplementedError("Media download is Milestone 4.")
