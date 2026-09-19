from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.settings import Settings
from app.core.versioning import DATASET_SCHEMA_VERSION
from app.main import app
from app.repositories.factory import (
    create_dataset_artifact_repository,
    create_saas_repository,
)
from app.saas.security import generate_api_key
from app.storage.local import LocalObjectStore


def test_entitled_user_can_download_local_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "download.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        saas_auth_enabled=True,
        saas_bootstrap_admin_key="bootstrap-secret",
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.saas.auth.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.storage.factory.get_settings",
        lambda: settings,
    )

    access = create_saas_repository(settings)
    user = access.create_user(
        email="reader@example.com",
        display_name="Reader",
        role="member",
        free_credits=1,
    )
    secret, prefix, digest = generate_api_key()
    access.create_api_key(
        user_id=int(user["id"]),
        name="test",
        key_prefix=prefix,
        key_hash=digest,
    )
    access.unlock_dataset(
        user_id=int(user["id"]),
        platform="xiaohongshu",
        post_id="post-1",
        is_admin=False,
    )

    source = tmp_path / "knowledge.md"
    source.write_text("# Dataset\nHello", encoding="utf-8")
    store = LocalObjectStore(settings.storage_local_dir)
    stored = store.put_file(
        source,
        key="xiaohongshu/posts/post-1/export/knowledge.md",
    )

    create_dataset_artifact_repository(settings).save(
        platform="xiaohongshu",
        post_id="post-1",
        dataset_schema_version=DATASET_SCHEMA_VERSION,
        storage_backend="local",
        export_prefix="xiaohongshu/posts/post-1/export",
        artifacts={"knowledge_markdown": stored.key},
    )

    with TestClient(app) as client:
        response = client.get(
            (
                "/api/saas/datasets/post-1/files/"
                "knowledge_markdown"
            ),
            headers={"X-API-Key": secret},
        )

    assert response.status_code == 200
    assert response.content == b"# Dataset\nHello"
