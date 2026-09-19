from typing import Any

from app.postgres.pool import pooled_connection


class PostgresLlmRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return pooled_connection(self.database_url)

    def create_connection(
        self,
        *,
        user_id: int,
        provider: str,
        label: str,
        model: str,
        base_url: str,
        secret_ciphertext: str,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO llm_connections (
                        user_id, provider, label, model,
                        base_url, secret_ciphertext
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        provider,
                        label,
                        model,
                        base_url,
                        secret_ciphertext,
                    ),
                )
                connection_id = int(cursor.fetchone()["id"])
        return self.get_connection(
            user_id=user_id,
            connection_id=connection_id,
        ) or {}

    def list_connections(self, *, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, provider, label, model,
                           base_url, enabled, created_at, updated_at
                    FROM llm_connections
                    WHERE user_id=%s
                    ORDER BY id DESC
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_connection(
        self,
        *,
        user_id: int,
        connection_id: int,
        include_secret: bool = False,
    ) -> dict[str, Any] | None:
        fields = (
            "id, user_id, provider, label, model, base_url, enabled, "
            "created_at, updated_at"
        )
        if include_secret:
            fields += ", secret_ciphertext"
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {fields}
                    FROM llm_connections
                    WHERE id=%s AND user_id=%s
                    """,
                    (connection_id, user_id),
                )
                row = cursor.fetchone()
        return dict(row) if row else None

    def disable_connection(
        self,
        *,
        user_id: int,
        connection_id: int,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE llm_connections
                    SET enabled=FALSE, updated_at=NOW()
                    WHERE id=%s AND user_id=%s
                    """,
                    (connection_id, user_id),
                )
                return cursor.rowcount == 1

    def create_run(
        self,
        *,
        user_id: int,
        post_id: str,
        connection_id: int,
        task: str,
        custom_instruction: str | None,
        input_schema_version: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO llm_organization_runs (
                        user_id, post_id, connection_id, task,
                        custom_instruction, input_schema_version
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        post_id,
                        connection_id,
                        task,
                        custom_instruction,
                        input_schema_version,
                    ),
                )
                return int(cursor.fetchone()["id"])

    def get_run(
        self,
        *,
        user_id: int,
        run_id: int,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM llm_organization_runs
                    WHERE id=%s AND user_id=%s
                    """,
                    (run_id, user_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["result"] = item.pop("result_json")
        return item

    def get_run_for_worker(self, *, run_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.*, c.provider, c.model, c.base_url,
                           c.secret_ciphertext, c.enabled
                    FROM llm_organization_runs r
                    JOIN llm_connections c ON c.id=r.connection_id
                    WHERE r.id=%s
                    """,
                    (run_id,),
                )
                row = cursor.fetchone()
        return dict(row) if row else None

    def mark_running(self, *, run_id: int) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE llm_organization_runs
                    SET status='RUNNING', started_at=NOW(), error=NULL
                    WHERE id=%s
                    """,
                    (run_id,),
                )

    def mark_complete(
        self,
        *,
        run_id: int,
        result: dict[str, Any],
    ) -> None:
        import json
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE llm_organization_runs
                    SET status='COMPLETE', result_json=%s::jsonb,
                        completed_at=NOW(), error=NULL
                    WHERE id=%s
                    """,
                    (
                        json.dumps(result, ensure_ascii=False),
                        run_id,
                    ),
                )

    def mark_failed(self, *, run_id: int, error: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE llm_organization_runs
                    SET status='FAILED', error=%s, completed_at=NOW()
                    WHERE id=%s
                    """,
                    (error[:4000], run_id),
                )

    def latest_for_post(
        self,
        *,
        user_id: int,
        post_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM llm_organization_runs
                    WHERE user_id=%s AND post_id=%s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (user_id, post_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["result"] = item.pop("result_json")
        return item
