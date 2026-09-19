import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.migrations import CURRENT_SCHEMA_VERSION
from app.core.settings import get_settings


def create_backup(output_dir: Path) -> Path:
    settings = get_settings()
    if settings.database_backend != "sqlite":
        raise RuntimeError(
            "creator-dataset-backup currently handles SQLite only. "
            "For PostgreSQL use managed database backups or pg_dump."
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = output_dir / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)

    database_target = backup_dir / "creator_dataset.sqlite3"
    source = sqlite3.connect(settings.database_path)
    destination = sqlite3.connect(database_target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deployment_mode": settings.deployment_mode,
        "database_backend": settings.database_backend,
        "database_schema_version": CURRENT_SCHEMA_VERSION,
        "storage_backend": settings.storage_backend,
        "database_file": database_target.name,
        "media_included": False,
        "notes": (
            "This backup contains transactional metadata only. "
            "Local object files or S3 objects must be backed up separately."
        ),
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return backup_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a safe Creator Dataset SQLite metadata backup."
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
