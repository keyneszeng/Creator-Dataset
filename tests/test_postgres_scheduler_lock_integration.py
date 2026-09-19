import os

import pytest

from app.postgres.runtime import PostgresSchedulerLock


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def test_only_one_scheduler_holds_advisory_lock() -> None:
    first = PostgresSchedulerLock(
        database_url=str(DATABASE_URL),
        lock_key=99887766,
    )
    second = PostgresSchedulerLock(
        database_url=str(DATABASE_URL),
        lock_key=99887766,
    )

    try:
        assert first.try_acquire() is True
        assert second.try_acquire() is False

        first.release()

        assert second.try_acquire() is True
    finally:
        first.release()
        second.release()
