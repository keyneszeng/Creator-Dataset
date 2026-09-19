from pathlib import Path

from app.core import database
from app.core.readiness import check_readiness
from app.core.settings import Settings


def test_deep_local_readiness_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="local",
        database_backend="sqlite",
        database_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.readiness.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.storage.factory.get_settings",
        lambda: settings,
    )

    result = check_readiness(deep_storage=True)

    assert result["ready"] is True
    assert result["checks"]["database"]["ok"] is True
    assert result["checks"]["storage"]["ok"] is True
