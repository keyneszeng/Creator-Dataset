import json
from typing import Any

from app.core.database import db_session


def ensure_checkpoint_table() -> None:
    with db_session() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY,
                platform TEXT NOT NULL,
                scope TEXT NOT NULL,
                object_id TEXT NOT NULL,
                cursor TEXT,
                finished BOOLEAN NOT NULL DEFAULT 0,
                metadata_json TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, scope, object_id)
            )
            """
        )


class CheckpointRepository:
    def get(
        self, *, platform: str, scope: str, object_id: str
    ) -> dict[str, Any] | None:
        ensure_checkpoint_table()
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT cursor, finished, metadata_json
                FROM checkpoints
                WHERE platform=? AND scope=? AND object_id=?
                """,
                (platform, scope, object_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "cursor": row["cursor"] or "",
            "finished": bool(row["finished"]),
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def save(
        self,
        *,
        platform: str,
        scope: str,
        object_id: str,
        cursor: str,
        finished: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ensure_checkpoint_table()
        with db_session() as connection:
            connection.execute(
                """
                INSERT INTO checkpoints (
                    platform, scope, object_id, cursor, finished, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, scope, object_id) DO UPDATE SET
                    cursor=excluded.cursor,
                    finished=excluded.finished,
                    metadata_json=excluded.metadata_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    platform,
                    scope,
                    object_id,
                    cursor,
                    int(finished),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
