from pathlib import Path

from fastapi.testclient import TestClient

from app.core import database
from app.core.settings import Settings
from app.main import app


def test_personal_cloud_token_protects_agent_rest_and_mcp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        environment="development",
        deployment_mode="cloud",
        database_backend="sqlite",
        database_path=tmp_path / "cloud.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        cloud_agent_token="top-secret",
        mcp_allowed_hosts="creator.example.com",
        agent_free_mode=True,
    )
    settings.ensure_directories()

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.agent.service.get_settings",
        lambda: settings,
    )

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200

        rest_denied = client.get("/v1/account")
        assert rest_denied.status_code == 401
        assert (
            rest_denied.json()["detail"]["code"]
            == "INVALID_AGENT_TOKEN"
        )

        rest_allowed = client.get(
            "/v1/account",
            headers={"Authorization": "Bearer top-secret"},
        )
        assert rest_allowed.status_code == 200
        assert rest_allowed.json()["mode"] == "free"

        mcp_denied = client.post("/mcp")
        assert mcp_denied.status_code == 401


def test_wrong_personal_cloud_token_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="sqlite",
        database_path=tmp_path / "wrong-token.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        cloud_agent_token="correct",
        mcp_allowed_hosts="creator.example.com",
    )
    settings.ensure_directories()

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get(
            "/v1/account",
            headers={"Authorization": "Bearer wrong"},
        )

    assert response.status_code == 401
