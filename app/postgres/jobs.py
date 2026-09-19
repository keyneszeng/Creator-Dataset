import json
from typing import Any

from app.core.errors import IntegrationNotInstalled
from app.postgres.schema import POSTGRES_JOB_SCHEMA


CLAIM_SQL = """
WITH candidate AS (
    SELECT j.id
    FROM jobs j
    WHERE j.status IN ('PENDING', 'RETRY')
      AND (j.next_retry_at IS NULL OR j.next_retry_at <= NOW())
      AND j.attempt < j.max_attempts
      AND NOT EXISTS (
          SELECT 1
          FROM job_dependencies d
          JOIN jobs dependency
            ON dependency.id=d.depends_on_job_id
          WHERE d.job_id=j.id
            AND dependency.status!='COMPLETE'
      )
    ORDER BY j.priority ASC, j.created_at ASC, j.id ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE jobs j
SET status='RUNNING',
    attempt=j.attempt + 1,
    retry_count=j.retry_count
        + CASE WHEN j.status='RETRY' THEN 1 ELSE 0 END,
    lease_owner=%s,
    lease_expires_at=NOW() + (%s * INTERVAL '1 second'),
    heartbeat_at=NOW(),
    started_at=COALESCE(j.started_at, NOW()),
    last_error=NULL
FROM candidate
WHERE j.id=candidate.id
RETURNING j.*;
"""


class PostgresJobRepository:
    """PostgreSQL durable queue implementation.

    This backend is implemented and contract-compatible, but the application
    does not enable database_backend=postgres until the remaining domain
    repositories have PostgreSQL implementations. This prevents split-brain
    SQLite/Postgres deployments.
    """

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required for PostgreSQL.")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise IntegrationNotInstalled(
                'Install PostgreSQL dependencies with pip install -e ".[postgres]".'
            ) from exc

        self.database_url = database_url
        self._psycopg = psycopg
        self._dict_row = dict_row

    def _connect(self):
        return self._psycopg.connect(
            self.database_url,
            row_factory=self._dict_row,
        )

    def init_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_JOB_SCHEMA)

    @staticmethod
    def _normalize(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        payload = result.get("payload_json")
        if isinstance(payload, str):
            result["payload"] = json.loads(payload or "{}")
        else:
            result["payload"] = payload or {}
        return result

    def enqueue(
        self,
        *,
        job_type: str,
        platform: str | None = None,
        creator_id: str | None = None,
        post_id: str | None = None,
        comment_id: str | None = None,
        parent_job_id: int | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        max_attempts: int = 5,
        depends_on: list[int] | None = None,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if idempotency_key:
                    cursor.execute(
                        "SELECT id FROM jobs WHERE idempotency_key=%s",
                        (idempotency_key,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        return int(existing["id"])

                cursor.execute("""
                    INSERT INTO jobs (
                        parent_job_id, idempotency_key, job_type, platform,
                        creator_id, post_id, comment_id, payload_json, status,
                        priority, max_attempts
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        'PENDING', %s, %s
                    )
                    RETURNING id
                """, (
                    parent_job_id,
                    idempotency_key,
                    job_type,
                    platform,
                    creator_id,
                    post_id,
                    comment_id,
                    json.dumps(payload or {}, ensure_ascii=False),
                    priority,
                    max_attempts,
                ))
                job_id = int(cursor.fetchone()["id"])

                for dependency_id in depends_on or []:
                    cursor.execute("""
                        INSERT INTO job_dependencies (
                            job_id, depends_on_job_id
                        ) VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (job_id, dependency_id))

                return job_id

    def create(
        self,
        *,
        job_type: str,
        platform: str | None = None,
        creator_id: str | None = None,
        post_id: str | None = None,
        comment_id: str | None = None,
    ) -> int:
        return self.enqueue(
            job_type=job_type,
            platform=platform,
            creator_id=creator_id,
            post_id=post_id,
            comment_id=comment_id,
        )

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(CLAIM_SQL, (worker_id, lease_seconds))
                return self._normalize(cursor.fetchone())

    def heartbeat(
        self,
        *,
        job_id: int,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET heartbeat_at=NOW(),
                        lease_expires_at=NOW()
                            + (%s * INTERVAL '1 second')
                    WHERE id=%s
                      AND status='RUNNING'
                      AND lease_owner=%s
                """, (lease_seconds, job_id, worker_id))
                return cursor.rowcount == 1

    def resolve_failed_dependencies(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs j
                    SET status='PARTIAL',
                        last_error=(
                            'A required dependency did not complete successfully.'
                        ),
                        completed_at=NOW(),
                        next_retry_at=NULL
                    WHERE j.status IN ('PENDING', 'RETRY')
                      AND EXISTS (
                          SELECT 1
                          FROM job_dependencies d
                          JOIN jobs dependency
                            ON dependency.id=d.depends_on_job_id
                          WHERE d.job_id=j.id
                            AND dependency.status IN (
                                'FAILED', 'PARTIAL', 'BLOCKED'
                            )
                      )
                """)
                return int(cursor.rowcount)

    def recover_expired_leases(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET status=CASE
                            WHEN attempt >= max_attempts THEN 'FAILED'
                            ELSE 'RETRY'
                        END,
                        last_error=CASE
                            WHEN attempt >= max_attempts
                            THEN COALESCE(
                                last_error,
                                'Worker lease expired; max attempts reached.'
                            )
                            ELSE COALESCE(
                                last_error,
                                'Worker lease expired; queued for retry.'
                            )
                        END,
                        next_retry_at=CASE
                            WHEN attempt >= max_attempts THEN NULL
                            ELSE NOW()
                        END,
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        heartbeat_at=NULL,
                        completed_at=CASE
                            WHEN attempt >= max_attempts THEN NOW()
                            ELSE NULL
                        END
                    WHERE status='RUNNING'
                      AND lease_expires_at IS NOT NULL
                      AND lease_expires_at < NOW()
                """)
                return int(cursor.rowcount)

    def schedule_retry(
        self,
        *,
        job_id: int,
        error: str,
        next_retry_at: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT attempt, max_attempts FROM jobs WHERE id=%s",
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return
                terminal = int(row["attempt"] or 0) >= int(
                    row["max_attempts"] or 0
                )
                cursor.execute("""
                    UPDATE jobs
                    SET status=%s,
                        last_error=%s,
                        next_retry_at=%s,
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        heartbeat_at=NULL,
                        completed_at=CASE
                            WHEN %s THEN NOW()
                            ELSE NULL
                        END
                    WHERE id=%s
                """, (
                    "FAILED" if terminal else "RETRY",
                    error,
                    None if terminal else next_retry_at,
                    terminal,
                    job_id,
                ))

    def mark_running(self, *, job_id: int) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET status='RUNNING',
                        started_at=COALESCE(started_at, NOW()),
                        last_error=NULL
                    WHERE id=%s
                """, (job_id,))

    def mark_waiting(self, *, job_id: int) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET status='WAITING',
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        heartbeat_at=NULL
                    WHERE id=%s
                """, (job_id,))

    def mark_complete(self, *, job_id: int) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET status='COMPLETE',
                        completed_at=NOW(),
                        next_retry_at=NULL,
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        heartbeat_at=NULL
                    WHERE id=%s
                """, (job_id,))

    def mark_failed(
        self,
        *,
        job_id: int,
        error: str,
        status: str = "FAILED",
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE jobs
                    SET status=%s,
                        last_error=%s,
                        completed_at=NOW(),
                        next_retry_at=NULL,
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        heartbeat_at=NULL
                    WHERE id=%s
                """, (status, error, job_id))

    def get_by_idempotency_key(
        self,
        *,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM jobs WHERE idempotency_key=%s",
                    (idempotency_key,),
                )
                return self._normalize(cursor.fetchone())

    def get(self, *, job_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM jobs WHERE id=%s",
                    (job_id,),
                )
                return self._normalize(cursor.fetchone())

    def dependencies(self, *, job_id: int) -> list[int]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT depends_on_job_id
                    FROM job_dependencies
                    WHERE job_id=%s
                    ORDER BY depends_on_job_id
                """, (job_id,))
                rows = cursor.fetchall()
        return [int(row["depends_on_job_id"]) for row in rows]

    def children_summary(self, *, parent_job_id: int) -> dict[str, int]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT status, COUNT(*) AS count
                    FROM jobs
                    WHERE parent_job_id=%s
                    GROUP BY status
                """, (parent_job_id,))
                rows = cursor.fetchall()
        summary = {
            str(row["status"]): int(row["count"])
            for row in rows
        }
        summary["TOTAL"] = sum(summary.values())
        return summary

    def reconcile_parent(self, *, parent_job_id: int) -> dict[str, int]:
        summary = self.children_summary(parent_job_id=parent_job_id)
        total = summary.get("TOTAL", 0)
        if total == 0:
            return summary

        terminal = (
            summary.get("COMPLETE", 0)
            + summary.get("PARTIAL", 0)
            + summary.get("FAILED", 0)
            + summary.get("BLOCKED", 0)
        )
        if terminal < total:
            return summary

        if (
            summary.get("FAILED", 0)
            or summary.get("PARTIAL", 0)
            or summary.get("BLOCKED", 0)
        ):
            self.mark_failed(
                job_id=parent_job_id,
                error=f"Child jobs finished with partial results: {summary}",
                status="PARTIAL",
            )
        else:
            self.mark_complete(job_id=parent_job_id)
        return summary

    def reconcile_ancestors(self, *, job_id: int) -> None:
        current = self.get(job_id=job_id)
        visited: set[int] = set()
        while current and current.get("parent_job_id"):
            parent_id = int(current["parent_job_id"])
            if parent_id in visited:
                break
            visited.add(parent_id)
            self.reconcile_parent(parent_job_id=parent_id)
            current = self.get(job_id=parent_id)

    def queue_summary(self) -> dict[str, int]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT status, COUNT(*) AS count
                    FROM jobs
                    GROUP BY status
                """)
                rows = cursor.fetchall()
        summary = {
            str(row["status"]): int(row["count"])
            for row in rows
        }
        summary["TOTAL"] = sum(summary.values())
        return summary

    def list_children(
        self,
        *,
        parent_job_id: int,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM jobs
                    WHERE parent_job_id=%s
                    ORDER BY id ASC
                    LIMIT %s
                """, (parent_job_id, limit))
                rows = cursor.fetchall()
        return [
            self._normalize(row)
            for row in rows
            if row is not None
        ]

    def job_tree(self, *, root_job_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    WITH RECURSIVE tree(
                        id, parent_job_id, depth
                    ) AS (
                        SELECT id, parent_job_id, 0
                        FROM jobs
                        WHERE id=%s
                        UNION ALL
                        SELECT j.id, j.parent_job_id, tree.depth + 1
                        FROM jobs j
                        JOIN tree ON j.parent_job_id=tree.id
                    )
                    SELECT j.*, tree.depth
                    FROM tree
                    JOIN jobs j ON j.id=tree.id
                    ORDER BY tree.depth ASC, j.id ASC
                """, (root_job_id,))
                rows = cursor.fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            item = self._normalize(row)
            if item is None:
                continue
            item["dependencies"] = self.dependencies(job_id=int(item["id"]))
            result.append(item)
        return result

    def repair_subgraph(self, *, job_id: int) -> list[int]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, parent_job_id FROM jobs WHERE id=%s",
                    (job_id,),
                )
                target = cursor.fetchone()
                if target is None:
                    return []

                cursor.execute("""
                    WITH RECURSIVE downstream(id) AS (
                        SELECT %s::bigint
                        UNION
                        SELECT d.job_id
                        FROM job_dependencies d
                        JOIN downstream p
                          ON d.depends_on_job_id=p.id
                    )
                    SELECT id FROM downstream
                """, (job_id,))
                repair_ids = [
                    int(row["id"])
                    for row in cursor.fetchall()
                ]

                cursor.execute("""
                    UPDATE jobs
                    SET status='PENDING',
                        attempt=0,
                        retry_count=0,
                        last_error=NULL,
                        next_retry_at=NULL,
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        heartbeat_at=NULL,
                        started_at=NULL,
                        completed_at=NULL
                    WHERE id=ANY(%s)
                      AND status IN (
                          'FAILED', 'PARTIAL', 'BLOCKED', 'COMPLETE'
                      )
                """, (repair_ids,))

                parent_id = target["parent_job_id"]
                visited: set[int] = set()
                while parent_id:
                    parent_int = int(parent_id)
                    if parent_int in visited:
                        break
                    visited.add(parent_int)

                    cursor.execute(
                        "SELECT parent_job_id FROM jobs WHERE id=%s",
                        (parent_int,),
                    )
                    parent = cursor.fetchone()
                    cursor.execute("""
                        UPDATE jobs
                        SET status='WAITING',
                            last_error=NULL,
                            completed_at=NULL
                        WHERE id=%s
                    """, (parent_int,))
                    parent_id = (
                        parent["parent_job_id"]
                        if parent
                        else None
                    )

                return repair_ids
