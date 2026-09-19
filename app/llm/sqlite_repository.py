import json
from typing import Any

from app.core.database import db_session


class SqliteLlmRepository:
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
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO llm_connections (
                    user_id, provider, label, model,
                    base_url, secret_ciphertext
                ) VALUES (?, ?, ?, ?, ?, ?)
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
            connection_id = int(cursor.lastrowid)
        return self.get_connection(
            user_id=user_id,
            connection_id=connection_id,
        ) or {}

    def list_connections(
        self,
        *,
        user_id: int,
    ) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, provider, label, model,
                       base_url, enabled, created_at, updated_at
                FROM llm_connections
                WHERE user_id=?
                ORDER BY id DESC
                """,
                (user_id,),
            ).fetchall()
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
        with db_session() as connection:
            row = connection.execute(
                f"""
                SELECT {fields}
                FROM llm_connections
                WHERE id=? AND user_id=?
                """,
                (connection_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def disable_connection(
        self,
        *,
        user_id: int,
        connection_id: int,
    ) -> bool:
        with db_session() as connection:
            cursor = connection.execute(
                """
                UPDATE llm_connections
                SET enabled=0, updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND user_id=?
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
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO llm_organization_runs (
                    user_id, post_id, connection_id, task,
                    custom_instruction, input_schema_version
                ) VALUES (?, ?, ?, ?, ?, ?)
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
        return int(cursor.lastrowid)

    def get_run(
        self,
        *,
        user_id: int,
        run_id: int,
    ) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM llm_organization_runs
                WHERE id=? AND user_id=?
                """,
                (run_id, user_id),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["result"] = (
            json.loads(item.pop("result_json"))
            if item.get("result_json")
            else None
        )
        return item

    def get_run_for_worker(self, *, run_id: int) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT r.*, c.provider, c.model, c.base_url,
                       c.secret_ciphertext, c.enabled
                FROM llm_organization_runs r
                JOIN llm_connections c ON c.id=r.connection_id
                WHERE r.id=?
                """,
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def mark_running(self, *, run_id: int) -> None:
        with db_session() as connection:
            connection.execute(
                """
                UPDATE llm_organization_runs
                SET status='RUNNING', started_at=CURRENT_TIMESTAMP,
                    error=NULL
                WHERE id=?
                """,
                (run_id,),
            )

    def mark_complete(
        self,
        *,
        run_id: int,
        result: dict[str, Any],
    ) -> None:
        with db_session() as connection:
            connection.execute(
                """
                UPDATE llm_organization_runs
                SET status='COMPLETE', result_json=?,
                    completed_at=CURRENT_TIMESTAMP, error=NULL
                WHERE id=?
                """,
                (json.dumps(result, ensure_ascii=False), run_id),
            )

    def mark_failed(self, *, run_id: int, error: str) -> None:
        with db_session() as connection:
            connection.execute(
                """
                UPDATE llm_organization_runs
                SET status='FAILED', error=?,
                    completed_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (error[:4000], run_id),
            )

    def latest_for_post(
        self,
        *,
        user_id: int,
        post_id: str,
    ) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM llm_organization_runs
                WHERE user_id=? AND post_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, post_id),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["result"] = (
            json.loads(item.pop("result_json"))
            if item.get("result_json")
            else None
        )
        return item
