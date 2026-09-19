import json
from typing import Any

from app.core.database import db_session


class CreatorRepository:
    def upsert(self, *, platform: str, creator_id: str, profile_url: str, name: str | None,
               avatar_url: str | None, bio: str | None, follower_count: int | None,
               following_count: int | None, raw: dict[str, Any]) -> None:
        with db_session() as connection:
            connection.execute("""
                INSERT INTO creators (
                    platform, creator_id, profile_url, name, avatar_url, bio,
                    follower_count, following_count, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, creator_id) DO UPDATE SET
                    profile_url=excluded.profile_url,
                    name=excluded.name,
                    avatar_url=excluded.avatar_url,
                    bio=excluded.bio,
                    follower_count=excluded.follower_count,
                    following_count=excluded.following_count,
                    raw_json=excluded.raw_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (platform, creator_id, profile_url, name, avatar_url, bio,
                  follower_count, following_count, json.dumps(raw, ensure_ascii=False)))

    def set_discovered_post_count(self, *, platform: str, creator_id: str, count: int) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE creators SET discovered_post_count=?, updated_at=CURRENT_TIMESTAMP
                WHERE platform=? AND creator_id=?
            """, (count, platform, creator_id))


class PostRepository:
    def upsert_discovered(self, *, platform: str, creator_id: str, post_id: str,
                          source_url: str | None, title: str | None, post_type: str | None,
                          raw: dict[str, Any], platform_context: dict[str, Any] | None = None) -> None:
        with db_session() as connection:
            connection.execute("""
                INSERT INTO posts (
                    platform, creator_id, post_id, source_url, title,
                    post_type, raw_json, platform_context_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, post_id) DO UPDATE SET
                    creator_id=excluded.creator_id,
                    source_url=COALESCE(excluded.source_url, posts.source_url),
                    title=COALESCE(excluded.title, posts.title),
                    post_type=COALESCE(excluded.post_type, posts.post_type),
                    raw_json=excluded.raw_json,
                    platform_context_json=excluded.platform_context_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (platform, creator_id, post_id, source_url, title, post_type,
                  json.dumps(raw, ensure_ascii=False),
                  json.dumps(platform_context or {}, ensure_ascii=False)))

    def list_for_detail(self, *, platform: str, creator_id: str, limit: int = 50,
                        only_missing: bool = True) -> list[dict[str, Any]]:
        query = """
            SELECT post_id, source_url, platform_context_json
            FROM posts WHERE platform=? AND creator_id=?
        """
        params: list[Any] = [platform, creator_id]
        if only_missing:
            query += " AND detail_raw_json IS NULL"
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        with db_session() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{
            "post_id": row["post_id"],
            "source_url": row["source_url"],
            "platform_context": json.loads(row["platform_context_json"] or "{}"),
        } for row in rows]

    def update_detail(self, *, platform: str, post_id: str, title: str | None,
                      content: str | None, post_type: str | None, published_at: int | str | None,
                      like_count: int | None, favorite_count: int | None, share_count: int | None,
                      reported_comment_count: int | None, raw: dict[str, Any]) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE posts SET
                    title=COALESCE(?, title),
                    content=?,
                    post_type=COALESCE(?, post_type),
                    published_at=?,
                    like_count=?,
                    favorite_count=?,
                    share_count=?,
                    reported_comment_count=?,
                    detail_raw_json=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE platform=? AND post_id=?
            """, (title, content, post_type, published_at, like_count, favorite_count,
                  share_count, reported_comment_count, json.dumps(raw, ensure_ascii=False),
                  platform, post_id))

    def get_access_context(self, *, platform: str, post_id: str) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute("""
                SELECT post_id, reported_comment_count, platform_context_json
                FROM posts WHERE platform=? AND post_id=?
            """, (platform, post_id)).fetchone()
        if row is None:
            return None
        return {
            "post_id": row["post_id"],
            "reported_comment_count": row["reported_comment_count"],
            "platform_context": json.loads(row["platform_context_json"] or "{}"),
        }

    def update_comment_progress(self, *, platform: str, post_id: str,
                                downloaded_comment_count: int, comment_status: str) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE posts
                SET downloaded_comment_count=?, comment_status=?, updated_at=CURRENT_TIMESTAMP
                WHERE platform=? AND post_id=?
            """, (downloaded_comment_count, comment_status, platform, post_id))

    def list_for_creator(
        self,
        *,
        platform: str,
        creator_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT post_id, detail_raw_json, comment_status
                FROM posts
                WHERE platform=? AND creator_id=?
                ORDER BY id ASC
                LIMIT ?
            """, (platform, creator_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def count_for_creator(self, *, platform: str, creator_id: str) -> int:
        with db_session() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS count FROM posts
                WHERE platform=? AND creator_id=?
            """, (platform, creator_id)).fetchone()
        return int(row["count"])


class CommentRepository:
    def upsert(self, *, platform: str, post_id: str, comment_id: str,
               root_comment_id: str | None, parent_comment_id: str | None,
               user_id: str | None, user_name: str | None, user_avatar: str | None,
               content: str | None, like_count: int | None, ip_location: str | None,
               published_at: int | str | None, depth: int, has_more_replies: bool,
               reply_count: int, pictures: list[Any], picture_urls: list[str],
               raw: dict[str, Any]) -> None:
        with db_session() as connection:
            connection.execute("""
                INSERT INTO comments (
                    platform, post_id, comment_id, root_comment_id, parent_comment_id,
                    user_id, user_name, user_avatar, content, like_count, ip_location,
                    published_at, depth, has_more_replies, reply_count, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, comment_id) DO UPDATE SET
                    root_comment_id=excluded.root_comment_id,
                    parent_comment_id=excluded.parent_comment_id,
                    user_id=excluded.user_id,
                    user_name=excluded.user_name,
                    user_avatar=excluded.user_avatar,
                    content=excluded.content,
                    like_count=excluded.like_count,
                    ip_location=excluded.ip_location,
                    published_at=excluded.published_at,
                    depth=excluded.depth,
                    has_more_replies=excluded.has_more_replies,
                    reply_count=excluded.reply_count,
                    raw_json=excluded.raw_json
            """, (platform, post_id, comment_id, root_comment_id, parent_comment_id,
                  user_id, user_name, user_avatar, content, like_count, ip_location,
                  published_at, depth, int(has_more_replies), reply_count,
                  json.dumps(raw, ensure_ascii=False)))

            for remote_url in picture_urls or []:
                connection.execute("""
                    INSERT OR IGNORE INTO media (
                        platform, post_id, comment_id, media_type, remote_url,
                        download_status
                    ) VALUES (?, ?, ?, 'comment_image', ?, 'PENDING')
                """, (platform, post_id, comment_id, remote_url))

    def list_roots_with_replies(self, *, platform: str, post_id: str) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT comment_id, reply_count, has_more_replies
                FROM comments
                WHERE platform=? AND post_id=? AND depth=0
                  AND (reply_count > 0 OR has_more_replies = 1)
                ORDER BY id ASC
            """, (platform, post_id)).fetchall()
        return [dict(row) for row in rows]

    def counts_for_post(self, *, platform: str, post_id: str) -> dict[str, int]:
        with db_session() as connection:
            row = connection.execute("""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN depth=0 THEN 1 ELSE 0 END) AS root_count,
                  SUM(CASE WHEN depth>0 THEN 1 ELSE 0 END) AS reply_count
                FROM comments
                WHERE platform=? AND post_id=?
            """, (platform, post_id)).fetchone()
        return {
            "total": int(row["total"] or 0),
            "root": int(row["root_count"] or 0),
            "reply": int(row["reply_count"] or 0),
        }


class AuditRepository:
    def save(self, *, post_id: str, expected_comments: int | None, actual_comments: int,
             root_comments: int, reply_comments: int, failed_threads: int,
             root_pagination_finished: bool, reply_threads_total: int,
             reply_threads_finished: int, pagination_finished: bool,
             completeness_ratio: float | None, status: str) -> None:
        with db_session() as connection:
            connection.execute("""
                INSERT INTO crawl_audits (
                    post_id, expected_comments, actual_comments, root_comments,
                    reply_comments, failed_threads, root_pagination_finished,
                    reply_threads_total, reply_threads_finished, pagination_finished,
                    completeness_ratio, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, expected_comments, actual_comments, root_comments, reply_comments,
                  failed_threads, int(root_pagination_finished), reply_threads_total,
                  reply_threads_finished, int(pagination_finished), completeness_ratio, status))



class MediaRepository:
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
        with db_session() as connection:
            connection.execute("""
                INSERT INTO media (
                    platform, post_id, comment_id, media_type, remote_url,
                    local_path, download_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
            row = connection.execute("""
                SELECT id FROM media
                WHERE platform=?
                  AND IFNULL(post_id, '')=IFNULL(?, '')
                  AND IFNULL(comment_id, '')=IFNULL(?, '')
                  AND media_type=?
                  AND remote_url=?
            """, (
                platform,
                post_id,
                comment_id,
                media_type,
                remote_url,
            )).fetchone()
        return int(row["id"])

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
        placeholders = ",".join("?" for _ in media_types)
        query = f"""
            SELECT id, post_id, comment_id, media_type, remote_url, local_path
            FROM media
            WHERE post_id=?
              AND media_type IN ({placeholders})
              AND download_status='COMPLETE'
              AND local_path IS NOT NULL
            ORDER BY id ASC
            LIMIT ?
        """
        params: list[Any] = [post_id, *media_types, limit]
        with db_session() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_local_videos(
        self,
        *,
        post_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT id, post_id, comment_id, media_type, remote_url, local_path
                FROM media
                WHERE post_id=?
                  AND media_type='video'
                  AND download_status='COMPLETE'
                  AND local_path IS NOT NULL
                ORDER BY id ASC
                LIMIT ?
            """, (post_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def list_pending_for_post(
        self,
        *,
        post_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT id, platform, post_id, comment_id, media_type, remote_url
                FROM media
                WHERE post_id=? AND download_status IN ('PENDING', 'FAILED')
                ORDER BY id ASC
                LIMIT ?
            """, (post_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def mark_downloading(self, *, media_id: int) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE media SET download_status='RUNNING' WHERE id=?
            """, (media_id,))

    def mark_downloaded(
        self,
        *,
        media_id: int,
        local_path: str,
        sha256: str | None = None,
    ) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE media
                SET local_path=?, sha256=?, download_status='COMPLETE'
                WHERE id=?
            """, (local_path, sha256, media_id))

    def mark_failed(self, *, media_id: int) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE media SET download_status='FAILED' WHERE id=?
            """, (media_id,))


class OcrRepository:
    def exists(self, *, media_id: int, engine: str) -> bool:
        with db_session() as connection:
            row = connection.execute("""
                SELECT 1 FROM ocr_results
                WHERE media_id=? AND engine=? AND status='COMPLETE'
                LIMIT 1
            """, (media_id, engine)).fetchone()
        return row is not None

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
        with db_session() as connection:
            connection.execute("""
                INSERT INTO ocr_results (
                    media_id, engine, engine_version, language, full_text,
                    average_confidence, blocks_json, status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'COMPLETE', NULL)
                ON CONFLICT(media_id, engine) DO UPDATE SET
                    engine_version=excluded.engine_version,
                    language=excluded.language,
                    full_text=excluded.full_text,
                    average_confidence=excluded.average_confidence,
                    blocks_json=excluded.blocks_json,
                    status='COMPLETE',
                    error=NULL,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                media_id,
                engine,
                engine_version,
                language,
                full_text,
                average_confidence,
                json.dumps(blocks, ensure_ascii=False),
            ))

    def save_error(self, *, media_id: int, engine: str, error: str) -> None:
        with db_session() as connection:
            connection.execute("""
                INSERT INTO ocr_results (
                    media_id, engine, full_text, status, error
                ) VALUES (?, ?, '', 'FAILED', ?)
                ON CONFLICT(media_id, engine) DO UPDATE SET
                    status='FAILED',
                    error=excluded.error,
                    updated_at=CURRENT_TIMESTAMP
            """, (media_id, engine, error))



class TranscriptRepository:
    def exists(
        self,
        *,
        media_id: int,
        engine: str,
        model: str,
    ) -> bool:
        with db_session() as connection:
            row = connection.execute("""
                SELECT 1 FROM transcripts
                WHERE media_id=? AND engine=? AND model=? AND status='COMPLETE'
                LIMIT 1
            """, (media_id, engine, model)).fetchone()
        return row is not None

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
        with db_session() as connection:
            connection.execute("""
                INSERT INTO transcripts (
                    media_id, engine, engine_version, model, language,
                    language_probability, full_text, segments_json, status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETE', NULL)
                ON CONFLICT(media_id, engine, model) DO UPDATE SET
                    engine_version=excluded.engine_version,
                    language=excluded.language,
                    language_probability=excluded.language_probability,
                    full_text=excluded.full_text,
                    segments_json=excluded.segments_json,
                    status='COMPLETE',
                    error=NULL,
                    updated_at=CURRENT_TIMESTAMP
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
        with db_session() as connection:
            connection.execute("""
                INSERT INTO transcripts (
                    media_id, engine, model, full_text, status, error
                ) VALUES (?, ?, ?, '', 'FAILED', ?)
                ON CONFLICT(media_id, engine, model) DO UPDATE SET
                    status='FAILED',
                    error=excluded.error,
                    updated_at=CURRENT_TIMESTAMP
            """, (media_id, engine, model, error))


class ExportRepository:
    def get_post_bundle(self, *, post_id: str) -> dict[str, Any] | None:
        with db_session() as connection:
            post = connection.execute("""
                SELECT * FROM posts WHERE post_id=?
            """, (post_id,)).fetchone()
            if post is None:
                return None

            comments = connection.execute("""
                SELECT * FROM comments
                WHERE post_id=?
                ORDER BY depth ASC, id ASC
            """, (post_id,)).fetchall()

            media = connection.execute("""
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
                    t.language_probability AS transcript_language_probability,
                    t.full_text AS transcript_text,
                    t.segments_json AS transcript_segments_json,
                    t.status AS transcript_status
                FROM media m
                LEFT JOIN ocr_results o ON o.media_id=m.id AND o.status='COMPLETE'
                LEFT JOIN transcripts t ON t.media_id=m.id AND t.status='COMPLETE'
                WHERE m.post_id=?
                ORDER BY m.id ASC
            """, (post_id,)).fetchall()

        return {
            "post": dict(post),
            "comments": [dict(row) for row in comments],
            "media": [dict(row) for row in media],
        }



class TextUnitRepository:
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
        with db_session() as connection:
            connection.execute("""
                INSERT INTO text_units (
                    source_key, platform, post_id, comment_id, media_id,
                    unit_type, text, confidence, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    text=excluded.text,
                    confidence=excluded.confidence,
                    provenance=excluded.provenance,
                    updated_at=CURRENT_TIMESTAMP
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
        with db_session() as connection:
            connection.execute(
                "DELETE FROM text_units WHERE post_id=?",
                (post_id,),
            )

    def list_for_post(self, *, post_id: str) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT * FROM text_units
                WHERE post_id=?
                ORDER BY id ASC
            """, (post_id,)).fetchall()
        return [dict(row) for row in rows]



class JobRepository:
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
    ) -> int:
        with db_session() as connection:
            if idempotency_key:
                row = connection.execute(
                    "SELECT id FROM jobs WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if row:
                    return int(row["id"])

            cursor = connection.execute("""
                INSERT INTO jobs (
                    parent_job_id, idempotency_key, job_type, platform,
                    creator_id, post_id, comment_id, payload_json, status,
                    priority, max_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
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
            return int(cursor.lastrowid)

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
        with db_session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("""
                SELECT *
                FROM jobs
                WHERE status IN ('PENDING', 'RETRY')
                  AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)
                  AND attempt < max_attempts
                ORDER BY priority ASC, created_at ASC, id ASC
                LIMIT 1
            """).fetchone()

            if row is None:
                return None

            job_id = int(row["id"])
            connection.execute("""
                UPDATE jobs
                SET status='RUNNING',
                    attempt=attempt + 1,
                    retry_count=retry_count + CASE WHEN status='RETRY' THEN 1 ELSE 0 END,
                    lease_owner=?,
                    lease_expires_at=datetime('now', ?),
                    heartbeat_at=CURRENT_TIMESTAMP,
                    started_at=COALESCE(started_at, CURRENT_TIMESTAMP),
                    last_error=NULL
                WHERE id=?
            """, (worker_id, f"+{lease_seconds} seconds", job_id))

            claimed = connection.execute(
                "SELECT * FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()

        result = dict(claimed)
        result["payload"] = json.loads(result.get("payload_json") or "{}")
        return result

    def heartbeat(
        self,
        *,
        job_id: int,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> bool:
        with db_session() as connection:
            cursor = connection.execute("""
                UPDATE jobs
                SET heartbeat_at=CURRENT_TIMESTAMP,
                    lease_expires_at=datetime('now', ?)
                WHERE id=? AND status='RUNNING' AND lease_owner=?
            """, (f"+{lease_seconds} seconds", job_id, worker_id))
        return cursor.rowcount == 1

    def recover_expired_leases(self) -> int:
        with db_session() as connection:
            cursor = connection.execute("""
                UPDATE jobs
                SET status=CASE
                        WHEN attempt >= max_attempts THEN 'FAILED'
                        ELSE 'RETRY'
                    END,
                    last_error=CASE
                        WHEN attempt >= max_attempts
                        THEN COALESCE(last_error, 'Worker lease expired; max attempts reached.')
                        ELSE COALESCE(last_error, 'Worker lease expired; queued for retry.')
                    END,
                    next_retry_at=CASE
                        WHEN attempt >= max_attempts THEN NULL
                        ELSE CURRENT_TIMESTAMP
                    END,
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    heartbeat_at=NULL,
                    completed_at=CASE
                        WHEN attempt >= max_attempts THEN CURRENT_TIMESTAMP
                        ELSE NULL
                    END
                WHERE status='RUNNING'
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < CURRENT_TIMESTAMP
            """)
        return int(cursor.rowcount)

    def schedule_retry(
        self,
        *,
        job_id: int,
        error: str,
        next_retry_at: str,
    ) -> None:
        with db_session() as connection:
            row = connection.execute(
                "SELECT attempt, max_attempts FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            terminal = int(row["attempt"] or 0) >= int(row["max_attempts"] or 0)
            connection.execute("""
                UPDATE jobs
                SET status=?,
                    last_error=?,
                    next_retry_at=?,
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    heartbeat_at=NULL,
                    completed_at=?
                WHERE id=?
            """, (
                "FAILED" if terminal else "RETRY",
                error,
                None if terminal else next_retry_at,
                "CURRENT_TIMESTAMP" if terminal else None,
                job_id,
            ))
            if terminal:
                connection.execute(
                    "UPDATE jobs SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                    (job_id,),
                )

    def mark_running(self, *, job_id: int) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE jobs
                SET status='RUNNING',
                    started_at=COALESCE(started_at, CURRENT_TIMESTAMP),
                    last_error=NULL
                WHERE id=?
            """, (job_id,))

    def mark_complete(self, *, job_id: int) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE jobs
                SET status='COMPLETE',
                    completed_at=CURRENT_TIMESTAMP,
                    next_retry_at=NULL,
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    heartbeat_at=NULL
                WHERE id=?
            """, (job_id,))

    def mark_failed(
        self,
        *,
        job_id: int,
        error: str,
        status: str = "FAILED",
    ) -> None:
        with db_session() as connection:
            connection.execute("""
                UPDATE jobs
                SET status=?,
                    last_error=?,
                    completed_at=CURRENT_TIMESTAMP,
                    next_retry_at=NULL,
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    heartbeat_at=NULL
                WHERE id=?
            """, (status, error, job_id))

    def get(self, *, job_id: int) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.get("payload_json") or "{}")
        return result

    def children_summary(self, *, parent_job_id: int) -> dict[str, int]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT status, COUNT(*) AS count
                FROM jobs
                WHERE parent_job_id=?
                GROUP BY status
            """, (parent_job_id,)).fetchall()
        summary = {str(row["status"]): int(row["count"]) for row in rows}
        summary["TOTAL"] = sum(summary.values())
        return summary

    def list_children(
        self,
        *,
        parent_job_id: int,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute("""
                SELECT *
                FROM jobs
                WHERE parent_job_id=?
                ORDER BY id ASC
                LIMIT ?
            """, (parent_job_id, limit)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.get("payload_json") or "{}")
            result.append(item)
        return result
