import json
from pathlib import Path

from app import backup
from app.core import database
from app.core.settings import Settings


def test_backup_creates_database_and_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "state.sqlite3",
        data_dir=tmp_path / "data",
        storage_local_dir=tmp_path / "objects",
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(backup, "get_settings", lambda: settings)

    backup_dir = backup.create_backup(tmp_path / "backups")

    assert (backup_dir / "creator_dataset.sqlite3").exists()
    manifest = json.loads(
        (backup_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["database_backend"] == "sqlite"
    assert manifest["media_included"] is False
