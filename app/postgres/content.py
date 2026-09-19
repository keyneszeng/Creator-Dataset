import json
from typing import Any

from app.core.errors import IntegrationNotInstalled
from app.postgres.creator_posts import _published_at
from app.postgres.schema import POSTGRES_CONTENT_SCHEMA


class _PostgresContentBase:
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
                cursor.execute(POSTGRES_CONTENT_SCHEMA)


class PostgresCommentRepository(_PostgresContentBase):
    def upsert(
        self,
        *,
        platform: str,
        post_id: str,
        comment_id: str,
        root_comment_id: str | None,
        parent_comment_id: str | None,
        user_id: str | None,
        user_name: str | None,
        user_avatar: str | None,
        content: str | None,
        like_count: int | None,
        ip_location: str | None,
        published_at: int | str | None,
        depth: int,
        has_more_replies: bool,
        reply_count: int,
        pictures: list[Any],
        picture_urls: list[str],
        raw: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO comments (
                        platform, post_id, comment_id, root_comment_id,
                        parent_comment_id, user_id, user_name, user_avatar,
                        content, like_count, ip_location, published_at, depth,
                        has_more_replies, reply_count, raw_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT(platform, comment_id) DO UPDATE SET
                        root_comment_id=EXCLUDED.root_comment_id,
                        parent_comment_id=EXCLUDED.parent_comment_id,
                        user_id=EXCLUDED.user_id,
                        user_name=EXCLUDED.user_name,
                        user_avatar=EXCLUDED.user_avatar,
                        content=EXCLUDED.content,
                        like_count=EXCLUDED.like_count,
                        ip_location=EXCLUDED.ip_location,
                        published_at=EXCLUDED.published_at,
                        depth=EXCLUDED.depth,
                        has_more_replies=EXCLUDED.has_more_replies,
                        reply_count=EXCLUDED.reply_count,
                        raw_json=EXCLUDED.raw_json
                """, (
                    platform,
                    post_id,
                    comment_id,
                    root_comment_id,
                    parent_comment_id,
                    user_id,
                    user_name,
                    user_avatar,
                    content,
                    like_count,
                    ip_location,
                    _published_at(published_at),
                    depth,
                    has_more_replies,
                    reply_count,
                    json.dumps(raw, ensure_ascii=False),
                ))

                for remote_url in picture_urls or []:
                    cursor.execute("""
                        INSERT INTO media (
                            platform, post_id, comment_id, media_type,
                            remote_url, download_status, is_active
                        ) VALUES (
                            %s, %s, %s, 'comment_image', %s, 'PENDING', TRUE
                        )
                        ON CONFLICT DO NOTHING
                    """, (
                        platform,
                        post_id,
                        comment_id,
                        remote_url,
                    ))

    def list_roots_with_replies(
        self,
        *,
        platform: str,
        post_id: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT comment_id, reply_count, has_more_replies
                    FROM comments
                    WHERE platform=%s AND post_id=%s AND depth=0
                      AND (reply_count > 0 OR has_more_replies=TRUE)
                    ORDER BY id ASC
                """, (platform, post_id))
                return [dict(row) for row in cursor.fetchall()]

    def counts_for_post(
        self,
        *,
        platform: str,
        post_id: str,
    ) -> dict[str, int]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE depth=0) AS root_count,
                        COUNT(*) FILTER (WHERE depth>0) AS reply_count
                    FROM comments
                    WHERE platform=%s AND post_id=%s
                """, (platform, post_id))
                row = cursor.fetchone()
        return {
            "total": int(row["total"] or 0),
            "root": int(row["root_count"] or 0),
            "reply": int(row["reply_count"] or 0),
        }


class PostgresAuditRepository(_PostgresContentBase):
    def save(
        self,
        *,
        post_id: str,
        expected_comments: int | None,
        actual_comments: int,
        root_comments: int,
        reply_comments: int,
        failed_threads: int,
        root_pagination_finished: bool,
        reply_threads_total: int,
        reply_threads_finished: int,
        pagination_finished: bool,
        completeness_ratio: float | None,
        status: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO crawl_audits (
                        post_id, expected_comments, actual_comments,
                        root_comments, reply_comments, failed_threads,
                        root_pagination_finished, reply_threads_total,
                        reply_threads_finished, pagination_finished,
                        completeness_ratio, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                """, (
                    post_id,
                    expected_comments,
                    actual_comments,
                    root_comments,
                    reply_comments,
                    failed_threads,
                    root_pagination_finished,
                    reply_threads_total,
                    reply_threads_finished,
                    pagination_finished,
                    completeness_ratio,
                    status,
                ))


class PostgresCheckpointRepository(_PostgresContentBase):
    def get(
        self,
        *,
        platform: str,
        scope: str,
        object_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT cursor, finished, metadata_json
                    FROM checkpoints
                    WHERE platform=%s AND scope=%s AND object_id=%s
                """, (platform, scope, object_id))
                row = cursor.fetchone()
        if row is None:
            return None
        return {
            "cursor": row["cursor"] or "",
            "finished": bool(row["finished"]),
            "metadata": row["metadata_json"] or {},
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
        with self._connect() as connection:
            with connection.cursor() as sql:
                sql.execute("""
                    INSERT INTO checkpoints (
                        platform, scope, object_id, cursor,
                        finished, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT(platform, scope, object_id) DO UPDATE SET
                        cursor=EXCLUDED.cursor,
                        finished=EXCLUDED.finished,
                        metadata_json=EXCLUDED.metadata_json,
                        updated_at=NOW()
                """, (
                    platform,
                    scope,
                    object_id,
                    cursor,
                    finished,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ))

    def count_finished_prefix(
        self,
        *,
        platform: str,
        scope: str,
        object_id_prefix: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM checkpoints
                    WHERE platform=%s
                      AND scope=%s
                      AND object_id LIKE %s
                      AND finished=TRUE
                """, (platform, scope, f"{object_id_prefix}%"))
                row = cursor.fetchone()
        return int(row["count"] or 0)

    def reset_comment_crawl(
        self,
        *,
        platform: str,
        post_id: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM checkpoints
                    WHERE platform=%s
                      AND scope='root_comments'
                      AND object_id=%s
                """, (platform, post_id))
                root_count = cursor.rowcount

                cursor.execute("""
                    DELETE FROM checkpoints
                    WHERE platform=%s
                      AND scope='sub_comments'
                      AND object_id LIKE %s
                """, (platform, f"{post_id}:%"))
                reply_count = cursor.rowcount

        return int(root_count) + int(reply_count)


class PostgresMediaRepository(_PostgresContentBase):
    def upsert(
        self,
        *,
        platform: str,
        post_id: str | None,
        comment_id: str | None,
        media_type: str,
        remote_url: str,
        local_path: str | None = None,
        download_status: str = "PENDING",
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO media (
                        platform, post_id, comment_id, media_type,
                        remote_url, local_path, download_status, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT DO NOTHING
                """, (
                    platform,
                    post_id,
                    comment_id,
                    media_type,
                    remote_url,
                    local_path,
                    download_status,
                ))
                cursor.execute("""
                    SELECT id
                    FROM media
                    WHERE platform=%s
                      AND COALESCE(post_id, '')=COALESCE(%s, '')
                      AND COALESCE(comment_id, '')=COALESCE(%s, '')
                      AND media_type=%s
                      AND remote_url=%s
                """, (
                    platform,
                    post_id,
                    comment_id,
                    media_type,
                    remote_url,
                ))
                row = cursor.fetchone()
                cursor.execute(
                    "UPDATE media SET is_active=TRUE WHERE id=%s",
                    (row["id"],),
                )
        return int(row["id"])

    def reconcile_post_media(
        self,
        *,
        platform: str,
        post_id: str,
        media_items: list[dict[str, str]],
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE media
                    SET is_active=FALSE
                    WHERE platform=%s
                      AND post_id=%s
                      AND comment_id IS NULL
                      AND media_type IN ('image', 'cover', 'video')
                """, (platform, post_id))

        for item in media_items:
            self.upsert(
                platform=platform,
                post_id=post_id,
                comment_id=None,
                media_type=item["media_type"],
                remote_url=item["remote_url"],
            )

    def list_local_images(
        self,
        *,
        post_id: str,
        include_comment_images: bool = True,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        media_types = ["image", "cover"]
        if include_comment_images:
            media_types.append("comment_image")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, post_id, comment_id, media_type, remote_url,
                           local_path, storage_backend, storage_key
                    FROM media
                    WHERE post_id=%s
                      AND media_type=ANY(%s)
                      AND download_status='COMPLETE'
                      AND is_active=TRUE
                      AND (
                          storage_key IS NOT NULL
                          OR local_path IS NOT NULL
                      )
                    ORDER BY id ASC
                    LIMIT %s
                """, (post_id, media_types, limit))
                return [dict(row) for row in cursor.fetchall()]

    def list_local_videos(
        self,
        *,
        post_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, post_id, comment_id, media_type, remote_url,
                           local_path, storage_backend, storage_key
                    FROM media
                    WHERE post_id=%s
                      AND media_type='video'
                      AND download_status='COMPLETE'
                      AND is_active=TRUE
                      AND (
                          storage_key IS NOT NULL
                          OR local_path IS NOT NULL
                      )
                    ORDER BY id ASC
                    LIMIT %s
                """, (post_id, limit))
                return [dict(row) for row in cursor.fetchall()]

    def list_pending_for_post(
        self,
        *,
        post_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, platform, post_id, comment_id,
                           media_type, remote_url
                    FROM media
                    WHERE post_id=%s
                      AND is_active=TRUE
                      AND download_status IN ('PENDING', 'FAILED')
                    ORDER BY id ASC
                    LIMIT %s
                """, (post_id, limit))
                return [dict(row) for row in cursor.fetchall()]

    def mark_downloading(self, *, media_id: int) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE media SET download_status='RUNNING' WHERE id=%s",
                    (media_id,),
                )

    def mark_downloaded(
        self,
        *,
        media_id: int,
        local_path: str | None,
        storage_backend: str,
        storage_key: str,
        sha256: str | None = None,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE media
                    SET local_path=%s,
                        storage_backend=%s,
                        storage_key=%s,
                        sha256=%s,
                        download_status='COMPLETE'
                    WHERE id=%s
                """, (
                    local_path,
                    storage_backend,
                    storage_key,
                    sha256,
                    media_id,
                ))

    def mark_failed(self, *, media_id: int) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE media SET download_status='FAILED' WHERE id=%s",
                    (media_id,),
                )


class PostgresOcrRepository(_PostgresContentBase):
    def exists(self, *, media_id: int, engine: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1
                    FROM ocr_results
                    WHERE media_id=%s
                      AND engine=%s
                      AND status='COMPLETE'
                    LIMIT 1
                """, (media_id, engine))
                return cursor.fetchone() is not None

    def save_result(
        self,
        *,
        media_id: int,
        engine: str,
        engine_version: str | None,
        language: str | None,
        full_text: str,
        average_confidence: float | None,
        blocks: list[dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ocr_results (
                        media_id, engine, engine_version, language,
                        full_text, average_confidence, blocks_json,
                        status, error
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s::jsonb,
                        'COMPLETE', NULL
                    )
                    ON CONFLICT(media_id, engine) DO UPDATE SET
                        engine_version=EXCLUDED.engine_version,
                        language=EXCLUDED.language,
                        full_text=EXCLUDED.full_text,
                        average_confidence=EXCLUDED.average_confidence,
                        blocks_json=EXCLUDED.blocks_json,
                        status='COMPLETE',
                        error=NULL,
                        updated_at=NOW()
                """, (
                    media_id,
                    engine,
                    engine_version,
                    language,
                    full_text,
                    average_confidence,
                    json.dumps(blocks, ensure_ascii=False),
                ))

    def save_error(
        self,
        *,
        media_id: int,
        engine: str,
        error: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ocr_results (
                        media_id, engine, full_text, status, error
                    ) VALUES (%s, %s, '', 'FAILED', %s)
                    ON CONFLICT(media_id, engine) DO UPDATE SET
                        status='FAILED',
                        error=EXCLUDED.error,
                        updated_at=NOW()
                """, (media_id, engine, error))


class PostgresTranscriptRepository(_PostgresContentBase):
    def exists(
        self,
        *,
        media_id: int,
        engine: str,
        model: str,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1
                    FROM transcripts
                    WHERE media_id=%s
                      AND engine=%s
                      AND model=%s
                      AND status='COMPLETE'
                    LIMIT 1
                """, (media_id, engine, model))
                return cursor.fetchone() is not None

    def save_result(
        self,
        *,
        media_id: int,
        engine: str,
        engine_version: str | None,
        model: str,
        language: str | None,
        language_probability: float | None,
        full_text: str,
        segments: list[dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO transcripts (
                        media_id, engine, engine_version, model,
                        language, language_probability, full_text,
                        segments_json, status, error
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, 'COMPLETE', NULL
                    )
                    ON CONFLICT(media_id, engine, model) DO UPDATE SET
                        engine_version=EXCLUDED.engine_version,
                        language=EXCLUDED.language,
                        language_probability=EXCLUDED.language_probability,
                        full_text=EXCLUDED.full_text,
                        segments_json=EXCLUDED.segments_json,
                        status='COMPLETE',
                        error=NULL,
                        updated_at=NOW()
                """, (
                    media_id,
                    engine,
                    engine_version,
                    model,
                    language,
                    language_probability,
                    full_text,
                    json.dumps(segments, ensure_ascii=False),
                ))

    def save_error(
        self,
        *,
        media_id: int,
        engine: str,
        model: str,
        error: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO transcripts (
                        media_id, engine, model, full_text, status, error
                    ) VALUES (%s, %s, %s, '', 'FAILED', %s)
                    ON CONFLICT(media_id, engine, model) DO UPDATE SET
                        status='FAILED',
                        error=EXCLUDED.error,
                        updated_at=NOW()
                """, (media_id, engine, model, error))


class PostgresTextUnitRepository(_PostgresContentBase):
    def upsert(
        self,
        *,
        source_key: str,
        platform: str,
        post_id: str,
        comment_id: str | None,
        media_id: int | None,
        unit_type: str,
        text: str,
        confidence: float | None,
        provenance: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO text_units (
                        source_key, platform, post_id, comment_id,
                        media_id, unit_type, text, confidence, provenance
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(source_key) DO UPDATE SET
                        text=EXCLUDED.text,
                        confidence=EXCLUDED.confidence,
                        provenance=EXCLUDED.provenance,
                        updated_at=NOW()
                """, (
                    source_key,
                    platform,
                    post_id,
                    comment_id,
                    media_id,
                    unit_type,
                    text,
                    confidence,
                    provenance,
                ))

    def delete_for_post(self, *, post_id: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM text_units WHERE post_id=%s",
                    (post_id,),
                )

    def list_for_post(
        self,
        *,
        post_id: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM text_units
                    WHERE post_id=%s
                    ORDER BY id ASC
                """, (post_id,))
                return [dict(row) for row in cursor.fetchall()]


class PostgresExportRepository(_PostgresContentBase):
    def get_post_bundle(
        self,
        *,
        post_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM posts WHERE post_id=%s",
                    (post_id,),
                )
                post = cursor.fetchone()
                if post is None:
                    return None

                cursor.execute("""
                    SELECT *
                    FROM comments
                    WHERE post_id=%s
                    ORDER BY depth ASC, id ASC
                """, (post_id,))
                comments = cursor.fetchall()

                cursor.execute("""
                    SELECT
                        m.*,
                        o.engine AS ocr_engine,
                        o.engine_version AS ocr_engine_version,
                        o.language AS ocr_language,
                        o.full_text AS ocr_text,
                        o.average_confidence AS ocr_confidence,
                        o.blocks_json AS ocr_blocks_json,
                        o.status AS ocr_status,
                        t.engine AS transcript_engine,
                        t.engine_version AS transcript_engine_version,
                        t.model AS transcript_model,
                        t.language AS transcript_language,
                        t.language_probability
                            AS transcript_language_probability,
                        t.full_text AS transcript_text,
                        t.segments_json AS transcript_segments_json,
                        t.status AS transcript_status
                    FROM media m
                    LEFT JOIN ocr_results o
                      ON o.media_id=m.id AND o.status='COMPLETE'
                    LEFT JOIN transcripts t
                      ON t.media_id=m.id AND t.status='COMPLETE'
                    WHERE m.post_id=%s AND m.is_active=TRUE
                    ORDER BY m.id ASC
                """, (post_id,))
                media = cursor.fetchall()

        return {
            "post": dict(post),
            "comments": [dict(row) for row in comments],
            "media": [dict(row) for row in media],
        }
