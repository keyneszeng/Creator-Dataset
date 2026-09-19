from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.settings import Settings
from app.main import app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        deployment_mode="local",
        database_backend="sqlite",
        database_path=tmp_path / "admin-api.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        saas_auth_enabled=True,
        saas_bootstrap_admin_key="bootstrap-secret",
        saas_default_free_dataset_credits=5,
    )


def test_admin_can_manage_user_and_rotate_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
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

    with TestClient(app) as client:
        admin = client.post(
            "/api/saas/admin/users",
            headers={"X-Bootstrap-Key": "bootstrap-secret"},
            json={
                "email": "admin@example.com",
                "role": "admin",
            },
        ).json()
        admin_key = admin["api_key"]

        member = client.post(
            "/api/saas/admin/users",
            headers={"X-API-Key": admin_key},
            json={
                "email": "member@example.com",
                "role": "member",
            },
        ).json()
        member_id = member["user"]["id"]
        original_key = member["api_key"]

        users = client.get(
            "/api/saas/admin/users",
            headers={"X-API-Key": admin_key},
        )
        assert users.status_code == 200
        assert users.json()["count"] == 2

        new_key = client.post(
            f"/api/saas/admin/users/{member_id}/api-keys",
            headers={"X-API-Key": admin_key},
            json={"name": "replacement"},
        )
        assert new_key.status_code == 200
        replacement_secret = new_key.json()["api_key"]

        keys = client.get(
            f"/api/saas/admin/users/{member_id}/api-keys",
            headers={"X-API-Key": admin_key},
        ).json()["items"]
        original = next(
            item for item in keys
            if item["key_prefix"] == original_key[:12]
        )

        revoked = client.post(
            (
                f"/api/saas/admin/users/{member_id}/api-keys/"
                f"{original['id']}/revoke"
            ),
            headers={"X-API-Key": admin_key},
        )
        assert revoked.status_code == 200

        assert client.get(
            "/api/saas/me",
            headers={"X-API-Key": original_key},
        ).status_code == 401

        assert client.get(
            "/api/saas/me",
            headers={"X-API-Key": replacement_secret},
        ).status_code == 200

        suspended = client.patch(
            f"/api/saas/admin/users/{member_id}",
            headers={"X-API-Key": admin_key},
            json={"status": "suspended"},
        )
        assert suspended.status_code == 200

        assert client.get(
            "/api/saas/me",
            headers={"X-API-Key": replacement_secret},
        ).status_code == 401
