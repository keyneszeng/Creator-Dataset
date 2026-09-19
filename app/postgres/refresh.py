import hashlib
import json
from typing import Any

from app.postgres.pool import pooled_connection
from app.postgres.schema import POSTGRES_REFRESH_SCHEMA


class _PostgresRefreshBase:
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required for PostgreSQL.")
        self.database_url = database_url

    def _connect(self):
        return pooled_connection(self.database_url)

    def init_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_REFRESH_SCHEMA)


class PostgresRawSnapshotRepository(_PostgresRefreshBase):
    def save(
        self,
        *,
        platform: str,
        resource_type: str,
        object_id: str,
        cursor: str | None,
        payload: dict[str, Any],
    ) -> int:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        with self._connect() as connection:
            with connection.cursor() as sql:
                sql.execute("""
                    INSERT INTO raw_snapshots (
                        platform, resource_type, object_id, cursor,
                        payload_sha256, payload_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                """, (
                    platform,
                    resource_type,
                    object_id,
                    cursor,
                    digest,
                    serialized,
                ))
                sql.execute("""
                    SELECT id
                    FROM raw_snapshots
                    WHERE platform=%s
                      AND resource_type=%s
                      AND object_id=%s
                      AND COALESCE(cursor, '')=COALESCE(%s, '')
                      AND payload_sha256=%s
                """, (
                    platform,
                    resource_type,
                    object_id,
                    cursor,
                    digest,
                ))
                row = sql.fetchone()
        return int(row["id"])

    def list_for_object(
        self,
        *,
        platform: str,
        resource_type: str,
        object_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, platform, resource_type, object_id,
                           cursor, payload_sha256, payload_json,
                           captured_at
                    FROM raw_snapshots
                    WHERE platform=%s
                      AND resource_type=%s
                      AND object_id=%s
                    ORDER BY id ASC
                    LIMIT %s
                """, (
                    platform,
                    resource_type,
                    object_id,
                    limit,
                ))
                rows = cursor.fetchall()

        return [{
            **dict(row),
            "payload": row["payload_json"],
        } for row in rows]


class PostgresChangeEventRepository(_PostgresRefreshBase):
    def record(
        self,
        *,
        platform: str,
        creator_id: str | None,
        post_id: str | None,
        entity_type: str,
        change_type: str,
        old_fingerprint: str | None,
        new_fingerprint: str | None,
        details: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO change_events (
                        platform, creator_id, post_id, entity_type,
                        change_type, old_fingerprint, new_fingerprint,
                        details_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id
                """, (
                    platform,
                    creator_id,
                    post_id,
                    entity_type,
                    change_type,
                    old_fingerprint,
                    new_fingerprint,
                    json.dumps(details or {}, ensure_ascii=False),
                ))
                return int(cursor.fetchone()["id"])

    def list_for_creator(
        self,
        *,
        platform: str,
        creator_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM change_events
                    WHERE platform=%s AND creator_id=%s
                    ORDER BY id DESC
                    LIMIT %s
                """, (platform, creator_id, limit))
                rows = cursor.fetchall()

        return [{
            **dict(row),
            "details": row["details_json"] or {},
        } for row in rows]


class PostgresRefreshRunRepository(_PostgresRefreshBase):
    def list_for_creator(
        self,
        *,
        platform: str,
        creator_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM refresh_runs
                    WHERE platform=%s AND creator_id=%s
                    ORDER BY id DESC
                    LIMIT %s
                """, (platform, creator_id, limit))
                return [dict(row) for row in cursor.fetchall()]

    def start(
        self,
        *,
        platform: str,
        creator_id: str,
        mode: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO refresh_runs (
                        platform, creator_id, mode, status
                    ) VALUES (%s, %s, %s, 'RUNNING')
                    RETURNING id
                """, (platform, creator_id, mode))
                return int(cursor.fetchone()["id"])

    def complete(
        self,
        *,
        refresh_run_id: int,
        new_posts: int,
        changed_posts: int,
        unchanged_posts: int,
        pages_scanned: int,
        status: str = "COMPLETE",
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE refresh_runs
                    SET new_posts=%s,
                        changed_posts=%s,
                        unchanged_posts=%s,
                        pages_scanned=%s,
                        status=%s,
                        completed_at=NOW()
                    WHERE id=%s
                """, (
                    new_posts,
                    changed_posts,
                    unchanged_posts,
                    pages_scanned,
                    status,
                    refresh_run_id,
                ))


class PostgresRefreshScheduleRepository(_PostgresRefreshBase):
    def upsert(
        self,
        *,
        platform: str,
        creator_id: str,
        interval_minutes: int,
        max_pages: int,
        max_recent_posts: int,
        stop_after_unchanged_pages: int,
        next_run_at: str,
        enabled: bool = True,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO refresh_schedules (
                        platform, creator_id, interval_minutes,
                        max_pages, max_recent_posts,
                        stop_after_unchanged_pages,
                        enabled, next_run_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT(platform, creator_id) DO UPDATE SET
                        interval_minutes=EXCLUDED.interval_minutes,
                        max_pages=EXCLUDED.max_pages,
                        max_recent_posts=EXCLUDED.max_recent_posts,
                        stop_after_unchanged_pages=
                            EXCLUDED.stop_after_unchanged_pages,
                        enabled=EXCLUDED.enabled,
                        next_run_at=EXCLUDED.next_run_at,
                        updated_at=NOW()
                    RETURNING id
                """, (
                    platform,
                    creator_id,
                    interval_minutes,
                    max_pages,
                    max_recent_posts,
                    stop_after_unchanged_pages,
                    enabled,
                    next_run_at,
                ))
                return int(cursor.fetchone()["id"])

    def due(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM refresh_schedules
                    WHERE enabled=TRUE
                      AND next_run_at <= NOW()
                    ORDER BY next_run_at ASC, id ASC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]

    def mark_enqueued(
        self,
        *,
        schedule_id: int,
        interval_minutes: int,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE refresh_schedules
                    SET last_run_at=NOW(),
                        next_run_at=NOW()
                            + (%s * INTERVAL '1 minute'),
                        updated_at=NOW()
                    WHERE id=%s
                """, (interval_minutes, schedule_id))

    def due_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        COUNT(*) FILTER (
                            WHERE enabled=TRUE
                              AND next_run_at <= NOW()
                        ) AS due,
                        COUNT(*) FILTER (
                            WHERE enabled=TRUE
                        ) AS enabled,
                        MIN(next_run_at) FILTER (
                            WHERE enabled=TRUE
                        ) AS next_run_at
                    FROM refresh_schedules
                """)
                row = cursor.fetchone()
        return {
            "due": int(row["due"] or 0),
            "enabled": int(row["enabled"] or 0),
            "next_run_at": row["next_run_at"],
        }

    def list_all(self, *, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM refresh_schedules
                    ORDER BY id ASC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]

    def set_enabled(
        self,
        *,
        schedule_id: int,
        enabled: bool,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE refresh_schedules
                    SET enabled=%s,
                        updated_at=NOW()
                    WHERE id=%s
                """, (enabled, schedule_id))
                return cursor.rowcount == 1
