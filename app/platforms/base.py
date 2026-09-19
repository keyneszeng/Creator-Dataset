from collections.abc import AsyncIterator
from typing import Any, Protocol


class PlatformAdapter(Protocol):
    platform: str

    async def resolve_creator(self, url: str) -> dict[str, Any]:
        ...

    async def get_creator(self, creator_id: str) -> dict[str, Any]:
        ...

    def iter_posts(self, creator_id: str) -> AsyncIterator[dict[str, Any]]:
        ...

    async def get_post(self, post_id: str) -> dict[str, Any]:
        ...

    def iter_root_comments(self, post_id: str) -> AsyncIterator[dict[str, Any]]:
        ...

    def iter_replies(
        self, post_id: str, root_comment_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        ...

    async def download_media(self, url: str, target_path: str) -> None:
        ...
