from pathlib import Path

from app.agent.service import AgentService
from app.core import database
from app.core.repositories import PostRepository
from app.core.settings import Settings


def test_local_agent_prepares_dataset_for_free(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "agent.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        agent_free_mode=True,
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.agent.service.get_settings",
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

    account = service.account_status()
    assert account["mode"] == "free"
    assert account["unlimited"] is True

    prepared = service.dataset_prepare("post-1")
    assert prepared["status"] == "PREPARING"
    assert prepared["free"] is True
    assert prepared["generation_job_id"] > 0


def test_agent_catalog_marks_posts_freely_available(
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
    monkeypatch.setattr(
        "app.agent.service.get_settings",
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

    assert result["items"][0]["available"] is True
