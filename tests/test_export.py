import json
from pathlib import Path

from app.core import database
from app.core.repositories import (
    ExportRepository,
    MediaRepository,
    OcrRepository,
    PostRepository,
)
from app.services.export import ExportService
from app.storage.base import StoredObject
from app.storage.local import LocalObjectStore


def _seed_post(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "export.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://www.xiaohongshu.com/explore/post-1",
        title="Title",
        post_type="normal",
        raw={},
        platform_context={},
    )
    posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="Author body",
        post_type="normal",
        published_at=1,
        like_count=1,
        favorite_count=1,
        share_count=1,
        reported_comment_count=0,
        raw={},
    )

    media = MediaRepository()
    media_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="image",
        remote_url="https://example.test/image.jpg",
        local_path="/tmp/image.jpg",
        download_status="COMPLETE",
    )
    OcrRepository().save_result(
        media_id=media_id,
        engine="fake",
        engine_version="1",
        language="ch",
        full_text="图片里的知识",
        average_confidence=0.99,
        blocks=[],
    )
    return media_id


def test_export_includes_ocr_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    media_id = _seed_post(tmp_path, monkeypatch)
    store = LocalObjectStore(tmp_path / "objects")

    result = ExportService(
        ExportRepository(),
        object_store=store,
    ).export_post("post-1")

    markdown = Path(result["knowledge_markdown"]).read_text(
        encoding="utf-8"
    )
    assert "Author body" in markdown
    assert "图片里的知识" in markdown
    assert f"Media {media_id}" in markdown

    manifest = json.loads(
        Path(result["manifest_json"]).read_text(encoding="utf-8")
    )
    assert manifest["dataset_schema_version"] == "0.2.0"
    assert manifest["post_id"] == "post-1"
    assert manifest["storage_backend"] == "local"
    assert manifest["files"]["analysis.jsonl"]["sha256"]
    assert store.exists(
        key="xiaohongshu/posts/post-1/export/analysis.jsonl"
    )


class FakeCloudStore:
    name = "s3"

    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    def put_file(self, source: Path, *, key: str) -> StoredObject:
        payload = source.read_bytes()
        self.uploaded[key] = payload
        return StoredObject(
            backend="s3",
            key=key,
            size=len(payload),
            local_path=None,
            uri=f"s3://test-bucket/prefix/{key}",
        )

    def exists(self, *, key: str) -> bool:
        return key in self.uploaded

    def delete(self, *, key: str) -> None:
        self.uploaded.pop(key, None)

    def materialize(self, *, key: str, suffix: str = ""):
        raise NotImplementedError


def test_export_returns_cloud_object_references(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_post(tmp_path, monkeypatch)
    store = FakeCloudStore()

    result = ExportService(
        ExportRepository(),
        object_store=store,
    ).export_post("post-1")

    assert result["storage_backend"] == "s3"
    assert result["knowledge_markdown"].startswith(
        "s3://test-bucket/prefix/"
    )
    assert result["manifest_json"].startswith(
        "s3://test-bucket/prefix/"
    )
    assert (
        "xiaohongshu/posts/post-1/export/manifest.json"
        in store.uploaded
    )
