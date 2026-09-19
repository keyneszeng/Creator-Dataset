import asyncio
import hashlib
import ipaddress
import mimetypes
import socket
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.core.repositories import MediaRepository
from app.storage.base import ObjectStore
from app.storage.factory import create_object_store


class UnsafeMediaUrl(ValueError):
    pass


def _validate_remote_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeMediaUrl("Only http/https media URLs are supported.")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UnsafeMediaUrl("Media URL has no hostname.")
    if host in {"localhost", "localhost.localdomain"}:
        raise UnsafeMediaUrl("Localhost media URLs are not allowed.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeMediaUrl(f"Could not resolve media hostname: {host}") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeMediaUrl("Private or local network media URLs are not allowed.")


def _suffix_for(content_type: str | None, url: str) -> str:
    parsed_suffix = Path(urlparse(url).path).suffix.lower()
    if 1 < len(parsed_suffix) <= 8:
        return parsed_suffix

    if content_type:
        mime = content_type.split(";", 1)[0].strip().lower()
        known = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/avif": ".avif",
            "image/gif": ".gif",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
        }
        if mime in known:
            return known[mime]
        guessed = mimetypes.guess_extension(mime)
        if guessed:
            return guessed
    return ".bin"


def _validate_content_type(media_type: str, content_type: str | None) -> None:
    if not content_type:
        return
    mime = content_type.split(";", 1)[0].strip().lower()
    if media_type in {"image", "cover", "comment_image"} and not mime.startswith("image/"):
        raise ValueError(f"Expected image media but received {mime}")
    if media_type == "video" and not (
        mime.startswith("video/") or mime == "application/octet-stream"
    ):
        raise ValueError(f"Expected video media but received {mime}")


def _storage_key(item: dict, suffix: str) -> str:
    post_id = str(item["post_id"])
    media_type = str(item["media_type"])
    filename = f"{item['id']}_{media_type}{suffix}"
    comment_id = item.get("comment_id")
    if comment_id:
        return (
            f"xiaohongshu/posts/{post_id}/comments/"
            f"{comment_id}/{filename}"
        )
    return f"xiaohongshu/posts/{post_id}/media/{filename}"


class MediaDownloadService:
    def __init__(
        self,
        *,
        repository: MediaRepository | None = None,
        object_store: ObjectStore | None = None,
        max_bytes: int = 250 * 1024 * 1024,
        max_redirects: int = 5,
    ) -> None:
        self.repository = repository or MediaRepository()
        self.object_store = object_store or create_object_store()
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects

    async def download_post_media(
        self,
        post_id: str,
        *,
        limit: int = 200,
    ) -> dict[str, int]:
        items = self.repository.list_pending_for_post(
            post_id=post_id,
            limit=limit,
        )
        downloaded = 0
        failed = 0

        for item in items:
            try:
                await self._download_one(item)
                downloaded += 1
            except Exception:
                self.repository.mark_failed(media_id=item["id"])
                failed += 1

        return {
            "downloaded": downloaded,
            "failed": failed,
            "total_candidates": len(items),
        }

    async def _download_one(self, item: dict) -> str:
        self.repository.mark_downloading(media_id=item["id"])

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/150 Safari/537.36"
            ),
            "Referer": "https://www.xiaohongshu.com/",
        }

        timeout = httpx.Timeout(30.0, connect=15.0)
        current_url = str(item["remote_url"])

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers=headers,
        ) as client:
            for redirect_count in range(self.max_redirects + 1):
                await asyncio.to_thread(_validate_remote_url, current_url)

                async with client.stream("GET", current_url) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Redirect response has no Location header.")
                        if redirect_count >= self.max_redirects:
                            raise ValueError("Too many media redirects.")
                        current_url = urljoin(current_url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type")
                    _validate_content_type(str(item["media_type"]), content_type)
                    suffix = _suffix_for(content_type, current_url)
                    key = _storage_key(item, suffix)

                    sha = hashlib.sha256()
                    total = 0
                    with tempfile.NamedTemporaryFile(
                        suffix=suffix,
                        delete=False,
                    ) as handle:
                        temp_path = Path(handle.name)

                    try:
                        with temp_path.open("wb") as file:
                            async for chunk in response.aiter_bytes():
                                total += len(chunk)
                                if total > self.max_bytes:
                                    raise ValueError(
                                        f"Media exceeds max size: {self.max_bytes} bytes"
                                    )
                                sha.update(chunk)
                                file.write(chunk)

                        stored = await asyncio.to_thread(
                            self.object_store.put_file,
                            temp_path,
                            key=key,
                        )
                    finally:
                        temp_path.unlink(missing_ok=True)

                    self.repository.mark_downloaded(
                        media_id=item["id"],
                        local_path=stored.local_path,
                        storage_backend=stored.backend,
                        storage_key=stored.key,
                        sha256=sha.hexdigest(),
                    )
                    return stored.key

        raise ValueError("Media download did not produce a terminal response.")
