from pathlib import Path

from app.core.capabilities import deployment_capabilities
from app.core.settings import Settings


def test_sqlite_reports_single_node_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="sqlite",
        database_path=tmp_path / "db.sqlite3",
        storage_backend="s3",
        s3_bucket="bucket",
    )
    monkeypatch.setattr(
        "app.core.capabilities.get_settings",
        lambda: settings,
    )

    result = deployment_capabilities()

    assert result["single_node_supported"] is True
    assert result["multi_host_workers_supported"] is False
    assert result["postgres_ready"] is False
    assert result["storage_backend"] == "s3"
