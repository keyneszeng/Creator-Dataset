import os

import pytest

from app.postgres.refresh import (
    PostgresChangeEventRepository,
    PostgresRawSnapshotRepository,
    PostgresRefreshRunRepository,
    PostgresRefreshScheduleRepository,
)


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def _init():
    snapshots = PostgresRawSnapshotRepository(str(DATABASE_URL))
    snapshots.init_schema()
    return snapshots


def _reset(repository) -> None:
    with repository._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE raw_snapshots, change_events, "
                "refresh_runs, refresh_schedules "
                "RESTART IDENTITY CASCADE"
            )


def test_raw_snapshot_deduplicates_by_content() -> None:
    snapshots = _init()
    _reset(snapshots)

    payload = {"items": [{"id": "a"}], "cursor": "next"}

    first = snapshots.save(
        platform="xiaohongshu",
        resource_type="creator_posts_page",
        object_id="creator-1",
        cursor="cursor-1",
        payload=payload,
    )
    second = snapshots.save(
        platform="xiaohongshu",
        resource_type="creator_posts_page",
        object_id="creator-1",
        cursor="cursor-1",
        payload=payload,
    )

    assert first == second
    rows = snapshots.list_for_object(
        platform="xiaohongshu",
        resource_type="creator_posts_page",
        object_id="creator-1",
    )
    assert len(rows) == 1
    assert rows[0]["payload"] == payload


def test_change_events_and_refresh_runs() -> None:
    snapshots = _init()
    _reset(snapshots)

    changes = PostgresChangeEventRepository(str(DATABASE_URL))
    changes.record(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        entity_type="post",
        change_type="comments_changed",
        old_fingerprint="a",
        new_fingerprint="b",
        details={"count": 2},
    )

    items = changes.list_for_creator(
        platform="xiaohongshu",
        creator_id="creator-1",
    )
    assert items[0]["change_type"] == "comments_changed"
    assert items[0]["details"] == {"count": 2}

    runs = PostgresRefreshRunRepository(str(DATABASE_URL))
    run_id = runs.start(
        platform="xiaohongshu",
        creator_id="creator-1",
        mode="incremental",
    )
    runs.complete(
        refresh_run_id=run_id,
        new_posts=1,
        changed_posts=2,
        unchanged_posts=3,
        pages_scanned=2,
    )
    row = runs.list_for_creator(
        platform="xiaohongshu",
        creator_id="creator-1",
    )[0]
    assert row["status"] == "COMPLETE"
    assert row["new_posts"] == 1


def test_refresh_schedule_due_and_advance() -> None:
    snapshots = _init()
    _reset(snapshots)

    schedules = PostgresRefreshScheduleRepository(str(DATABASE_URL))
    schedule_id = schedules.upsert(
        platform="xiaohongshu",
        creator_id="creator-1",
        interval_minutes=60,
        max_pages=3,
        max_recent_posts=30,
        stop_after_unchanged_pages=2,
        next_run_at="2000-01-01 00:00:00+00",
        enabled=True,
    )

    due = schedules.due()
    assert due[0]["id"] == schedule_id

    schedules.mark_enqueued(
        schedule_id=schedule_id,
        interval_minutes=60,
    )

    summary = schedules.due_summary()
    assert summary["enabled"] == 1
    assert summary["due"] == 0
