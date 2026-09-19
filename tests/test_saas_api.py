from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.repositories import PostRepository
from app.core.settings import Settings
from app.main import app


def test_member_gets_five_datasets_then_needs_paid_credit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="local",
        database_backend="sqlite",
        database_path=tmp_path / "saas-api.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        saas_auth_enabled=True,
        saas_bootstrap_admin_key="bootstrap-secret",
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

    posts = PostRepository()
    for index in range(6):
        posts.upsert_discovered(
            platform="xiaohongshu",
            creator_id="creator-1",
            post_id=f"post-{index}",
            source_url=f"https://www.xiaohongshu.com/explore/post-{index}",
            title=f"Post {index}",
            post_type="normal",
            raw={},
            platform_context={},
        )

    with TestClient(app) as client:
        created = client.post(
            "/api/saas/admin/users",
            headers={"X-Bootstrap-Key": "bootstrap-secret"},
            json={
                "email": "member@example.com",
                "display_name": "Member",
                "role": "member",
            },
        )
        assert created.status_code == 200
        body = created.json()
        user_id = body["user"]["id"]
        api_key = body["api_key"]
        assert body["free_dataset_credits"] == 5

        auth = {"X-API-Key": api_key}
        me = client.get("/api/saas/me", headers=auth)
        assert me.status_code == 200
        assert me.json()["credits"]["free"] == 5

        # Member cannot bypass the SaaS layer via internal operational APIs.
        internal = client.get("/api/jobs/999", headers=auth)
        assert internal.status_code == 403

        for index in range(5):
            unlocked = client.post(
                f"/api/saas/datasets/post-{index}/unlock",
                headers=auth,
            )
            assert unlocked.status_code == 200
            assert unlocked.json()["source"] == "free_credit"

        sixth = client.post(
            "/api/saas/datasets/post-5/unlock",
            headers=auth,
        )
        assert sixth.status_code == 402
        assert sixth.json()["detail"]["code"] == "PAYMENT_REQUIRED"

        grant = client.post(
            f"/api/saas/admin/users/{user_id}/credits",
            headers={"X-Bootstrap-Key": "bootstrap-secret"},
            json={
                "bucket": "paid",
                "amount": 10,
                "reason": "test_purchase",
            },
        )
        assert grant.status_code == 200
        assert grant.json()["credits"]["paid"] == 10

        paid_unlock = client.post(
            "/api/saas/datasets/post-5/unlock",
            headers=auth,
        )
        assert paid_unlock.status_code == 200
        assert paid_unlock.json()["source"] == "paid_credit"

        dataset = client.get(
            "/api/saas/datasets/post-5",
            headers=auth,
        )
        assert dataset.status_code == 200
        assert dataset.json()["ready"] is False
        assert dataset.json()["generation_job"] is not None
