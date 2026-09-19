from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.repositories import PostRepository
from app.core.settings import Settings
from app.core.versioning import DATASET_SCHEMA_VERSION
from app.main import app
from app.repositories.factory import (
    create_dataset_artifact_repository,
    create_saas_repository,
)
from app.saas.security import generate_api_key


def test_creator_catalog_is_free_and_workspace_scoped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "catalog.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        saas_auth_enabled=True,
        saas_bootstrap_admin_key="bootstrap",
        saas_default_free_dataset_credits=5,
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.saas.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.saas.service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )

    access = create_saas_repository(settings)
    user = access.create_user(
        email="catalog@example.com",
        display_name="Catalog",
        role="member",
        free_credits=5,
    )
    user_id = int(user["id"])
    secret, prefix, digest = generate_api_key()
    access.create_api_key(
        user_id=user_id,
        name="catalog",
        key_prefix=prefix,
        key_hash=digest,
    )
    access.record_creator_submission(
        user_id=user_id,
        platform="xiaohongshu",
        creator_id="creator-1",
        submitted_url=(
            "https://www.xiaohongshu.com/user/profile/creator-1"
        ),
    )

    posts = PostRepository()
    for index in range(2):
        posts.upsert_discovered(
            platform="xiaohongshu",
            creator_id="creator-1",
            post_id=f"post-{index}",
            source_url=(
                f"https://www.xiaohongshu.com/explore/post-{index}"
            ),
            title=f"Post {index}",
            post_type="normal",
            raw={},
            platform_context={},
        )

    access.unlock_dataset(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-0",
        is_admin=False,
    )
    create_dataset_artifact_repository(settings).save(
        platform="xiaohongshu",
        post_id="post-0",
        dataset_schema_version=DATASET_SCHEMA_VERSION,
        storage_backend="local",
        export_prefix="x/post-0/export",
        artifacts={"knowledge_markdown": "x/post-0/export/knowledge.md"},
    )

    auth = {"X-API-Key": secret}
    with TestClient(app) as client:
        before = client.get(
            "/api/saas/me",
            headers=auth,
        ).json()["credits"]

        catalog = client.get(
            "/api/saas/creators/creator-1/posts",
            headers=auth,
        )
        assert catalog.status_code == 200
        body = catalog.json()
        assert body["total"] == 2

        by_id = {
            item["post_id"]: item
            for item in body["items"]
        }
        assert by_id["post-0"]["unlocked"] is True
        assert by_id["post-0"]["dataset_ready"] is True
        assert by_id["post-0"]["unlock_cost_credits"] == 0

        assert by_id["post-1"]["unlocked"] is False
        assert by_id["post-1"]["dataset_ready"] is False
        assert by_id["post-1"]["unlock_cost_credits"] == 1
        assert by_id["post-1"]["can_unlock"] is True

        after = client.get(
            "/api/saas/me",
            headers=auth,
        ).json()["credits"]

        forbidden = client.get(
            "/api/saas/creators/not-submitted/posts",
            headers=auth,
        )

    # Catalog browsing itself consumes no credits.
    assert before == after
    assert before["free"] == 4
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == (
        "CREATOR_NOT_IN_WORKSPACE"
    )
