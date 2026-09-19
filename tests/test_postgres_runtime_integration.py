import os

import pytest

from app.postgres.jobs import PostgresJobRepository
from app.postgres.runtime import (
    PostgresSharedRateLimiter,
    PostgresWorkerRepository,
)


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def _init() -> None:
    PostgresJobRepository(str(DATABASE_URL)).init_schema()


def test_worker_heartbeat_visible_across_connections() -> None:
    _init()
    workers = PostgresWorkerRepository(str(DATABASE_URL))

    workers.touch(worker_id="worker-a", current_job_id=None)

    active = PostgresWorkerRepository(str(DATABASE_URL)).active(
        stale_after_seconds=60
    )

    assert any(item["worker_id"] == "worker-a" for item in active)


def test_rate_limit_slot_is_shared_across_instances() -> None:
    _init()

    first = PostgresSharedRateLimiter(
        database_url=str(DATABASE_URL),
        key="xhs-test-rate",
        min_interval_seconds=1.0,
    )
    second = PostgresSharedRateLimiter(
        database_url=str(DATABASE_URL),
        key="xhs-test-rate",
        min_interval_seconds=1.0,
    )

    with first._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM rate_limits WHERE key=%s",
                ("xhs-test-rate",),
            )

    first_delay = first.reserve_delay()
    second_delay = second.reserve_delay()

    assert first_delay < 0.1
    assert second_delay > 0.8
