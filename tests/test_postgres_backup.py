from pathlib import Path

from app import backup
from app.core.settings import Settings


def test_postgres_backup_uses_pg_dump(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="postgres",
        database_url="postgresql://user:pass@example/db",
        data_dir=tmp_path / "data",
        storage_backend="s3",
        s3_bucket="bucket",
    )

    calls: list[list[str]] = []

    monkeypatch.setattr(backup, "get_settings", lambda: settings)
    monkeypatch.setattr(backup.shutil, "which", lambda _: "/usr/bin/pg_dump")
    monkeypatch.setattr(
        backup,
        "postgres_schema_version",
        lambda _: 2,
    )

    def fake_run(args, check):
        calls.append(args)
        target_arg = next(
            arg for arg in args if arg.startswith("--file=")
        )
        Path(target_arg.split("=", 1)[1]).write_bytes(b"dump")
        return None

    monkeypatch.setattr(backup.subprocess, "run", fake_run)

    backup_dir = backup.create_backup(tmp_path / "backups")

    assert (backup_dir / "creator_dataset.dump").exists()
    assert calls
    assert calls[0][0] == "/usr/bin/pg_dump"
    assert "--format=custom" in calls[0]
