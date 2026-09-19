from pathlib import Path

from app.agent.service import AgentService
from app.core import database
from app.core.repositories import PostRepository
from app.core.settings import Settings


def test_local_agent_requires_explicit_unlock_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "agent.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="Post 1",
        post_type="normal",
        raw={},
        platform_context={},
    )

    service = AgentService()

    preview = service.dataset_unlock(
        "post-1",
        confirm=False,
    )
    assert preview["status"] == "CONFIRMATION_REQUIRED"
    assert preview["credit_cost"] == 0

    unlocked = service.dataset_unlock(
        "post-1",
        confirm=True,
    )
    assert unlocked["status"] == "UNLOCKED"
    assert unlocked["charged"] is False
    assert unlocked["generation_job_id"] > 0


def test_agent_catalog_does_not_mark_admin_posts_unlocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "catalog.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="Post 1",
        post_type="normal",
        raw={},
        platform_context={},
    )

    service = AgentService()
    result = service.creator_posts("creator-1")

    assert result["items"][0]["unlocked"] is False
