from typing import Any

from app.postgres.pool import pooled_connection


class PostgresDatasetArtifactRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return pooled_connection(self.database_url)

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
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dataset_artifacts (
                        platform, post_id, dataset_schema_version,
                        storage_backend, export_prefix, artifacts_json
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(platform, post_id, dataset_schema_version)
                    DO UPDATE SET
                        storage_backend=EXCLUDED.storage_backend,
                        export_prefix=EXCLUDED.export_prefix,
                        artifacts_json=EXCLUDED.artifacts_json,
                        generated_at=NOW()
                    """,
                    (
                        platform,
                        post_id,
                        dataset_schema_version,
                        storage_backend,
                        export_prefix,
                        artifacts,
                    ),
                )

    def get(
        self,
        *,
        platform: str,
        post_id: str,
        dataset_schema_version: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM dataset_artifacts
                    WHERE platform=%s AND post_id=%s
                      AND dataset_schema_version=%s
                    """,
                    (platform, post_id, dataset_schema_version),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["artifacts"] = item.pop("artifacts_json")
        return item


    def ready_post_ids(
        self,
        *,
        platform: str,
        post_ids: list[str],
        dataset_schema_version: str,
    ) -> set[str]:
        if not post_ids:
            return set()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT post_id
                    FROM dataset_artifacts
                    WHERE platform=%s
                      AND dataset_schema_version=%s
                      AND post_id = ANY(%s)
                    """,
                    (platform, dataset_schema_version, post_ids),
                )
                rows = cursor.fetchall()
        return {str(row["post_id"]) for row in rows}
