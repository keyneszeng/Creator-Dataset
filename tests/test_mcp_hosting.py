from pathlib import Path

import pytest

from app.core.settings import Settings
from app.mcp_hosting import build_mcp_asgi_app


def test_cloud_mcp_requires_explicit_allowed_hosts(
    tmp_path: Path,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="sqlite",
        database_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        cloud_agent_token="secret",
        mcp_allowed_hosts="",
    )

    with pytest.raises(ValueError):
        build_mcp_asgi_app(settings)


def test_cloud_mcp_builds_with_allowed_host(
    tmp_path: Path,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="sqlite",
        database_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        cloud_agent_token="secret",
        mcp_allowed_hosts="creator.example.com,creator.example.com:443",
    )

    app = build_mcp_asgi_app(settings)

    assert app is not None
