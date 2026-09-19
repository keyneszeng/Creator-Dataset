from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.settings import Settings
from app.main import app
from app.repositories.factory import create_saas_repository
from app.saas.security import generate_api_key


def _create_member(repository, email: str) -> str:
    user = repository.create_user(
        email=email,
        display_name=email,
        role="member",
        free_credits=5,
    )
    secret, prefix, digest = generate_api_key()
    repository.create_api_key(
        user_id=int(user["id"]),
        name="test",
        key_prefix=prefix,
        key_hash=digest,
    )
    return secret


def test_creator_submit_returns_202_and_shares_import_job(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "submission.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        saas_auth_enabled=True,
        saas_bootstrap_admin_key="bootstrap",
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

    repository = create_saas_repository(settings)
    key_a = _create_member(repository, "a@example.com")
    key_b = _create_member(repository, "b@example.com")

    url = (
        "https://www.xiaohongshu.com/user/profile/"
        "creator123?xsec_token=secret"
    )

    with TestClient(app) as client:
        first = client.post(
            "/api/saas/creators/submit",
            headers={"X-API-Key": key_a},
            json={"url": url, "max_pages": 20},
        )
        second = client.post(
            "/api/saas/creators/submit",
            headers={"X-API-Key": key_b},
            json={"url": url, "max_pages": 20},
        )

        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["creator_id"] == "creator123"
        assert (
            first.json()["canonical_url"]
            == "https://www.xiaohongshu.com/user/profile/creator123"
        )
        assert first.json()["import_job_id"] == second.json()["import_job_id"]
        assert first.json()["status"] == "PENDING"

        status = client.get(
            "/api/saas/creators/creator123/status",
            headers={"X-API-Key": key_a},
        )

    assert status.status_code == 200
    body = status.json()
    assert body["import_job"]["job_type"] == "CREATOR_IMPORT"
    assert body["discovered_posts"] == 0
