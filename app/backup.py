import argparse
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.core.migrations import CURRENT_SCHEMA_VERSION
from app.core.settings import get_settings
from app.postgres.database import postgres_schema_version


def _timestamped_dir(output_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = output_dir / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    return backup_dir


def _sqlite_backup(backup_dir: Path) -> tuple[str, int]:
    settings = get_settings()
    database_target = backup_dir / "creator_dataset.sqlite3"

    source = sqlite3.connect(settings.database_path)
    destination = sqlite3.connect(database_target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    return database_target.name, CURRENT_SCHEMA_VERSION


def _postgres_backup(backup_dir: Path) -> tuple[str, int]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("PostgreSQL database_url is not configured.")

    executable = shutil.which("pg_dump")
    if executable is None:
        raise RuntimeError(
            "pg_dump is required for PostgreSQL backups. "
            "Install the PostgreSQL client tools."
        )

    target = backup_dir / "creator_dataset.dump"
    subprocess.run(
        [
            executable,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            f"--file={target}",
            settings.database_url,
        ],
        check=True,
    )
    return target.name, postgres_schema_version(settings.database_url)


def create_backup(output_dir: Path) -> Path:
    settings = get_settings()
    backup_dir = _timestamped_dir(output_dir)

    try:
        if settings.database_backend == "sqlite":
            database_file, schema_version = _sqlite_backup(backup_dir)
        elif settings.database_backend == "postgres":
            database_file, schema_version = _postgres_backup(backup_dir)
        else:
            raise RuntimeError(
                f"Unsupported database backend: {settings.database_backend}"
            )

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "deployment_mode": settings.deployment_mode,
            "database_backend": settings.database_backend,
            "database_schema_version": schema_version,
            "storage_backend": settings.storage_backend,
            "database_file": database_file,
            "media_included": False,
            "notes": (
                "This backup contains transactional metadata only. "
                "Object storage must be protected separately."
            ),
        }
        (backup_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return backup_dir

    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a Creator Dataset metadata backup "
            "(SQLite online backup or PostgreSQL pg_dump)."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backups"),
        help="Directory that will contain timestamped backups.",
    )
    args = parser.parse_args()
    backup_dir = create_backup(args.output)
    print(str(backup_dir))


if __name__ == "__main__":
    main()
