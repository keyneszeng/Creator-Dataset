from pathlib import Path

from app.core.capabilities import deployment_capabilities
from app.core.settings import Settings


def test_postgres_with_local_storage_is_not_full_multi_host(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="postgres",
        database_url="postgresql://example/test",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
    )
    monkeypatch.setattr(
        "app.core.capabilities.get_settings",
        lambda: settings,
    )

    result = deployment_capabilities()

    assert result["multi_host_database_coordination_supported"] is True
    assert result["multi_host_workers_supported"] is False


def test_postgres_and_s3_enable_full_multi_host(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="postgres",
        database_url="postgresql://example/test",
        data_dir=tmp_path / "data",
        storage_backend="s3",
        s3_bucket="bucket",
    )
    monkeypatch.setattr(
        "app.core.capabilities.get_settings",
        lambda: settings,
    )

    result = deployment_capabilities()

    assert result["multi_host_workers_supported"] is True
