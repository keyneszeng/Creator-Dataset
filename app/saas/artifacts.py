import json
from typing import Any

from app.core.database import db_session


class SqliteDatasetArtifactRepository:
    def save(
        self,
        *,
        platform: str,
        post_id: str,
        dataset_schema_version: str,
        storage_backend: str,
        export_prefix: str,
        artifacts: dict[str, str],
    ) -> None:
        with db_session() as connection:
            connection.execute(
                """
                INSERT INTO dataset_artifacts (
                    platform, post_id, dataset_schema_version,
                    storage_backend, export_prefix, artifacts_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, post_id, dataset_schema_version)
                DO UPDATE SET
                    storage_backend=excluded.storage_backend,
                    export_prefix=excluded.export_prefix,
                    artifacts_json=excluded.artifacts_json,
                    generated_at=CURRENT_TIMESTAMP
                """,
                (
                    platform,
                    post_id,
                    dataset_schema_version,
                    storage_backend,
                    export_prefix,
                    json.dumps(artifacts, ensure_ascii=False),
                ),
            )

    def get(
        self,
        *,
        platform: str,
        post_id: str,
        dataset_schema_version: str,
    ) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM dataset_artifacts
                WHERE platform=? AND post_id=? AND dataset_schema_version=?
                """,
                (platform, post_id, dataset_schema_version),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["artifacts"] = json.loads(item.pop("artifacts_json"))
        return item
