import asyncio
import time

from app.core.database import db_session


class SharedRateLimiter:
    """Cross-worker minimum-interval limiter backed by SQLite.

    V0.1 goal: smooth bursts across multiple local worker processes.
    This is not a substitute for platform-specific adaptive throttling.
    """

    def __init__(self, *, key: str, min_interval_seconds: float) -> None:
        self.key = key
        self.min_interval_seconds = max(min_interval_seconds, 0.0)

    def reserve_delay(self) -> float:
        now = time.time()
        with db_session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT next_allowed_at FROM rate_limits WHERE key=?",
                (self.key,),
            ).fetchone()

            previous = float(row["next_allowed_at"]) if row else 0.0
            slot = max(now, previous)
            next_allowed = slot + self.min_interval_seconds

            connection.execute(
                """
                INSERT INTO rate_limits (key, next_allowed_at)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    next_allowed_at=excluded.next_allowed_at,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (self.key, next_allowed),
            )

        return max(slot - now, 0.0)

    async def wait(self) -> None:
        delay = await asyncio.to_thread(self.reserve_delay)
        if delay > 0:
            await asyncio.sleep(delay)


def create_shared_rate_limiter(
    *,
    key: str,
    min_interval_seconds: float,
):
    from app.core.settings import get_settings

    settings = get_settings()
    if settings.database_backend == "sqlite":
        return SharedRateLimiter(
            key=key,
            min_interval_seconds=min_interval_seconds,
        )

    if not settings.database_url:
        raise ValueError(
            "database_url is required for PostgreSQL rate limiting."
        )
    from app.postgres.runtime import PostgresSharedRateLimiter
    return PostgresSharedRateLimiter(
        database_url=settings.database_url,
        key=key,
        min_interval_seconds=min_interval_seconds,
    )
