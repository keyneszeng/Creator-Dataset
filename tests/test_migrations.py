import sqlite3
from pathlib import Path

from app.core import database
from app.core.migrations import CURRENT_SCHEMA_VERSION


def test_database_records_current_schema_version(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.sqlite3"
    database.init_database(db_path)

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
    finally:
        connection.close()

    assert row[0] == CURRENT_SCHEMA_VERSION
