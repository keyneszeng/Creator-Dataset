import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.versioning import DATASET_SCHEMA_VERSION, PIPELINE_API_VERSION
from app.repositories.factory import (
    create_creator_repository,
    create_post_repository,
)
from app.storage.base import ObjectStore, StoredObject
from app.storage.factory import create_object_store


class CreatorExportService:
    def __init__(
        self,
        *,
        creators: Any | None = None,
        posts: Any | None = None,
        object_store: ObjectStore | None = None,
    ) -> None:
        self.creators = creators or create_creator_repository()
        self.posts = posts or create_post_repository()
        self.object_store = object_store or create_object_store()

    def export_creator(
        self,
        creator_id: str,
        *,
        max_posts: int = 10000,
    ) -> dict[str, Any]:
        creator = self.creators.get(
            platform="xiaohongshu",
            creator_id=creator_id,
        )
        if creator is None:
            raise ValueError(f"Unknown creator: {creator_id}")

        posts = self.posts.list_for_creator(
            platform="xiaohongshu",
            creator_id=creator_id,
            limit=max_posts,
        )
        prefix = f"xiaohongshu/creators/{creator_id}/export"

        post_entries: list[dict[str, Any]] = []
        complete = 0
        missing = 0

        for post in posts:
            post_id = str(post["post_id"])
            manifest_key = (
                f"xiaohongshu/posts/{post_id}/export/manifest.json"
            )
            exists = self.object_store.exists(key=manifest_key)
            if exists:
                complete += 1
            else:
                missing += 1

            post_entries.append({
                "post_id": post_id,
                "comment_status": post.get("comment_status"),
                "detail_complete": post.get("detail_raw_json") is not None,
                "post_manifest_key": manifest_key,
                "export_available": exists,
            })

        status = "COMPLETE" if missing == 0 else "PARTIAL"

        creator_doc = self._jsonable(dict(creator))
        manifest = {
            "dataset_schema_version": DATASET_SCHEMA_VERSION,
            "pipeline_api_version": PIPELINE_API_VERSION,
            "platform": "xiaohongshu",
            "creator_id": creator_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "storage_backend": self.object_store.name,
            "export_prefix": prefix,
            "status": status,
            "posts": {
                "total": len(post_entries),
                "export_available": complete,
                "export_missing": missing,
            },
        }

        with tempfile.TemporaryDirectory(
            prefix=f"creator-dataset-creator-{creator_id}-"
        ) as temp_dir:
            directory = Path(temp_dir)
            creator_path = directory / "creator.json"
            posts_path = directory / "posts.jsonl"
            manifest_path = directory / "manifest.json"

            creator_path.write_text(
                json.dumps(
                    creator_doc,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            posts_path.write_text(
                "".join(
                    json.dumps(
                        entry,
                        ensure_ascii=False,
                        default=str,
                    ) + "\n"
                    for entry in post_entries
                ),
                encoding="utf-8",
            )

            files = {
                "creator.json": creator_path,
                "posts.jsonl": posts_path,
            }
            manifest["files"] = {
                name: {
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest(),
                    "storage_key": f"{prefix}/{name}",
                }
                for name, path in files.items()
            }
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            files["manifest.json"] = manifest_path

            stored = {
                name: self.object_store.put_file(
                    path,
                    key=f"{prefix}/{name}",
                )
                for name, path in files.items()
            }

        return {
            "creator_id": creator_id,
            "status": status,
            "post_count": len(post_entries),
            "missing_post_exports": missing,
            "creator_json": self._reference(stored["creator.json"]),
            "posts_jsonl": self._reference(stored["posts.jsonl"]),
            "manifest_json": self._reference(stored["manifest.json"]),
            "export_prefix": prefix,
            "storage_backend": self.object_store.name,
        }

    @staticmethod
    def _reference(stored: StoredObject) -> str:
        if stored.local_path:
            return stored.local_path
        if stored.uri:
            return stored.uri
        return f"{stored.backend}://{stored.key}"

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: CreatorExportService._jsonable(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [
                CreatorExportService._jsonable(item)
                for item in value
            ]
        return value
