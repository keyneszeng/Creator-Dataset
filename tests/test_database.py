from pathlib import Path

from app.core.database import db_session, init_database


def test_init_database_creates_core_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    init_database(database_path)

    with db_session(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

    names = {row["name"] for row in rows}
    assert {
        "creators",
        "posts",
        "comments",
        "media",
        "jobs",
        "crawl_audits",
    }.issubset(names)
