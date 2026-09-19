import json
from pathlib import Path

from app.core import database
from app.core.repositories import CreatorRepository, PostRepository
from app.services.creator_export import CreatorExportService
from app.storage.local import LocalObjectStore


def test_creator_bundle_reports_missing_post_exports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "creator-export.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    creators = CreatorRepository()
    posts = PostRepository()
    store = LocalObjectStore(tmp_path / "objects")

    creators.upsert(
        platform="xiaohongshu",
        creator_id="creator-1",
        profile_url="https://example.test/creator-1",
        name="Creator",
        avatar_url=None,
        bio="bio",
        follower_count=10,
        following_count=2,
        raw={"id": "creator-1"},
    )

    for post_id in ("post-1", "post-2"):
        posts.upsert_discovered(
            platform="xiaohongshu",
            creator_id="creator-1",
            post_id=post_id,
            source_url=f"https://example.test/{post_id}",
            title=post_id,
            post_type="normal",
            raw={},
            platform_context={},
        )

    existing_manifest = tmp_path / "post-manifest.json"
    existing_manifest.write_text("{}", encoding="utf-8")
    store.put_file(
        existing_manifest,
        key="xiaohongshu/posts/post-1/export/manifest.json",
    )

    result = CreatorExportService(
        creators=creators,
        posts=posts,
        object_store=store,
    ).export_creator("creator-1")

    assert result["status"] == "PARTIAL"
    assert result["post_count"] == 2
    assert result["missing_post_exports"] == 1

    manifest = json.loads(
        Path(result["manifest_json"]).read_text(encoding="utf-8")
    )
    assert manifest["posts"]["export_available"] == 1
    assert manifest["posts"]["export_missing"] == 1

    post_rows = Path(result["posts_jsonl"]).read_text(
        encoding="utf-8"
    ).splitlines()
    entries = [json.loads(row) for row in post_rows]
    assert entries[0]["post_id"] == "post-1"
    assert entries[0]["export_available"] is True
    assert entries[1]["export_available"] is False
