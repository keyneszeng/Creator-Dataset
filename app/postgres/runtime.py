import time
from typing import Any

from app.postgres.jobs import PostgresJobRepository


class PostgresWorkerRepository:
    def __init__(self, database_url: str) -> None:
        self.jobs = PostgresJobRepository(database_url)
        self.database_url = database_url

    def _connect(self):
        return self.jobs._connect()

    def touch(
        self,
        *,
        worker_id: str,
        current_job_id: int | None = None,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO workers (
                        worker_id, current_job_id, heartbeat_at
                    ) VALUES (%s, %s, NOW())
                    ON CONFLICT(worker_id) DO UPDATE SET
                        current_job_id=EXCLUDED.current_job_id,
                        heartbeat_at=NOW()
                """, (worker_id, current_job_id))

    def clear_job(self, *, worker_id: str) -> None:
        self.touch(worker_id=worker_id, current_job_id=None)

    def active(
        self,
        *,
        stale_after_seconds: int = 180,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT worker_id, current_job_id, started_at, heartbeat_at
                    FROM workers
                    WHERE heartbeat_at >= NOW()
                        - (%s * INTERVAL '1 second')
                    ORDER BY heartbeat_at DESC
                """, (stale_after_seconds,))
                return [dict(row) for row in cursor.fetchall()]

    def prune_stale(self, *, stale_after_seconds: int = 86400) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM workers
                    WHERE heartbeat_at < NOW()
                        - (%s * INTERVAL '1 second')
                """, (stale_after_seconds,))
                return int(cursor.rowcount)


class PostgresSharedRateLimiter:
    """Cross-host request pacing backed by PostgreSQL row locking."""

    def __init__(
        self,
        *,
        database_url: str,
        key: str,
        min_interval_seconds: float,
    ) -> None:
        self.jobs = PostgresJobRepository(database_url)
        self.key = key
        self.min_interval_seconds = max(min_interval_seconds, 0.0)

    def _connect(self):
        return self.jobs._connect()

    def reserve_delay(self) -> float:
        now = time.time()

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO rate_limits (key, next_allowed_at)
                    VALUES (%s, 0)
                    ON CONFLICT(key) DO NOTHING
                """, (self.key,))

                cursor.execute("""
                    SELECT next_allowed_at
                    FROM rate_limits
                    WHERE key=%s
                    FOR UPDATE
                """, (self.key,))
                row = cursor.fetchone()

                previous = float(row["next_allowed_at"] or 0.0)
                slot = max(now, previous)
                next_allowed = slot + self.min_interval_seconds

                cursor.execute("""
                    UPDATE rate_limits
                    SET next_allowed_at=%s,
                        updated_at=NOW()
                    WHERE key=%s
                """, (next_allowed, self.key))

        return max(slot - now, 0.0)
