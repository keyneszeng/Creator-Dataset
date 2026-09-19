from pathlib import Path

from app.core import database
from app.core.rate_limit import SharedRateLimiter


def test_shared_rate_limiter_reserves_future_slot(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "rate.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    limiter = SharedRateLimiter(
        key="xiaohongshu-api",
        min_interval_seconds=1.0,
    )

    first = limiter.reserve_delay()
    second = limiter.reserve_delay()

    assert first < 0.1
    assert second > 0.8
