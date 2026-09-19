import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.core.errors import IntegrationNotInstalled
from app.postgres.schema import POSTGRES_CREATOR_POST_SCHEMA


def _fingerprint(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _published_at(value: int | str | None):
    if value is None:
        return None
    if isinstance(value, int):
        # Xiaohongshu timestamps may be ms or seconds.
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            numeric = int(stripped)
            seconds = numeric / 1000 if numeric > 10_000_000_000 else numeric
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        return value
    return value


class _PostgresBase:
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
                cursor.execute(POSTGRES_CREATOR_POST_SCHEMA)


class PostgresCreatorRepository(_PostgresBase):
    def upsert(
        self,
        *,
        platform: str,
        creator_id: str,
        profile_url: str,
        name: str | None,
        avatar_url: str | None,
        bio: str | None,
        follower_count: int | None,
        following_count: int | None,
        raw: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO creators (
                        platform, creator_id, profile_url, name, avatar_url,
                        bio, follower_count, following_count, raw_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT(platform, creator_id) DO UPDATE SET
                        profile_url=EXCLUDED.profile_url,
                        name=EXCLUDED.name,
                        avatar_url=EXCLUDED.avatar_url,
                        bio=EXCLUDED.bio,
                        follower_count=EXCLUDED.follower_count,
                        following_count=EXCLUDED.following_count,
                        raw_json=EXCLUDED.raw_json,
                        updated_at=NOW()
                """, (
                    platform,
                    creator_id,
                    profile_url,
                    name,
                    avatar_url,
                    bio,
                    follower_count,
                    following_count,
                    json.dumps(raw, ensure_ascii=False),
                ))

    def get(
        self,
        *,
        platform: str,
        creator_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT *
                    FROM creators
                    WHERE platform=%s AND creator_id=%s
                """, (platform, creator_id))
                row = cursor.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["raw"] = result.pop("raw_json") or {}
        return result

    def set_discovered_post_count(
        self,
        *,
        platform: str,
        creator_id: str,
        count: int,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE creators
                    SET discovered_post_count=%s,
                        updated_at=NOW()
                    WHERE platform=%s AND creator_id=%s
                """, (count, platform, creator_id))


class PostgresPostRepository(_PostgresBase):
    def upsert_discovered(
        self,
        *,
        platform: str,
        creator_id: str,
        post_id: str,
        source_url: str | None,
        title: str | None,
        post_type: str | None,
        raw: dict[str, Any],
        platform_context: dict[str, Any] | None = None,
    ) -> str:
        fingerprint = _fingerprint({
            "title": title,
            "post_type": post_type,
            "raw": raw,
        })

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT discovery_fingerprint
                    FROM posts
                    WHERE platform=%s AND post_id=%s
                """, (platform, post_id))
                existing = cursor.fetchone()

                cursor.execute("""
                    INSERT INTO posts (
                        platform, creator_id, post_id, source_url, title,
                        post_type, raw_json, platform_context_json,
                        discovery_fingerprint, last_discovered_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s, NOW()
                    )
                    ON CONFLICT(platform, post_id) DO UPDATE SET
                        creator_id=EXCLUDED.creator_id,
                        source_url=COALESCE(
                            EXCLUDED.source_url,
                            posts.source_url
                        ),
                        title=COALESCE(EXCLUDED.title, posts.title),
                        post_type=COALESCE(
                            EXCLUDED.post_type,
                            posts.post_type
                        ),
                        raw_json=EXCLUDED.raw_json,
                        platform_context_json=EXCLUDED.platform_context_json,
                        discovery_fingerprint=EXCLUDED.discovery_fingerprint,
                        last_discovered_at=NOW(),
                        updated_at=NOW()
                """, (
                    platform,
                    creator_id,
                    post_id,
                    source_url,
                    title,
                    post_type,
                    json.dumps(raw, ensure_ascii=False),
                    json.dumps(platform_context or {}, ensure_ascii=False),
                    fingerprint,
                ))

        if existing is None:
            return "NEW"
        if existing["discovery_fingerprint"] != fingerprint:
            return "CHANGED"
        return "UNCHANGED"

    def list_for_detail(
        self,
        *,
        platform: str,
        creator_id: str,
        limit: int = 50,
        only_missing: bool = True,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT post_id, source_url, platform_context_json
            FROM posts
            WHERE platform=%s AND creator_id=%s
        """
        params: list[Any] = [platform, creator_id]
        if only_missing:
            query += " AND detail_raw_json IS NULL"
        query += " ORDER BY id ASC LIMIT %s"
        params.append(limit)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

        return [{
            "post_id": row["post_id"],
            "source_url": row["source_url"],
            "platform_context": row["platform_context_json"] or {},
        } for row in rows]

    def update_detail(
        self,
        *,
        platform: str,
        post_id: str,
        title: str | None,
        content: str | None,
        post_type: str | None,
        published_at: int | str | None,
        like_count: int | None,
        favorite_count: int | None,
        share_count: int | None,
        reported_comment_count: int | None,
        raw: dict[str, Any],
        media: list[dict[str, Any]] | None = None,
    ) -> dict[str, bool]:
        content_fingerprint = _fingerprint({
            "title": title,
            "content": content,
            "post_type": post_type,
            "published_at": published_at,
        })
        media_fingerprint = _fingerprint(media or [])
        engagement_fingerprint = _fingerprint({
            "like_count": like_count,
            "favorite_count": favorite_count,
            "share_count": share_count,
        })
        comments_fingerprint = _fingerprint({
            "reported_comment_count": reported_comment_count,
        })
        detail_fingerprint = _fingerprint({
            "content": content_fingerprint,
            "media": media_fingerprint,
            "engagement": engagement_fingerprint,
            "comments": comments_fingerprint,
        })

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT detail_fingerprint, content_fingerprint,
                           media_fingerprint, engagement_fingerprint,
                           comments_fingerprint
                    FROM posts
                    WHERE platform=%s AND post_id=%s
                """, (platform, post_id))
                existing = cursor.fetchone()

                cursor.execute("""
                    UPDATE posts SET
                        title=COALESCE(%s, title),
                        content=%s,
                        post_type=COALESCE(%s, post_type),
                        published_at=%s,
                        like_count=%s,
                        favorite_count=%s,
                        share_count=%s,
                        reported_comment_count=%s,
                        detail_raw_json=%s::jsonb,
                        detail_fingerprint=%s,
                        content_fingerprint=%s,
                        media_fingerprint=%s,
                        engagement_fingerprint=%s,
                        comments_fingerprint=%s,
                        last_refreshed_at=NOW(),
                        updated_at=NOW()
                    WHERE platform=%s AND post_id=%s
                """, (
                    title,
                    content,
                    post_type,
                    _published_at(published_at),
                    like_count,
                    favorite_count,
                    share_count,
                    reported_comment_count,
                    json.dumps(raw, ensure_ascii=False),
                    detail_fingerprint,
                    content_fingerprint,
                    media_fingerprint,
                    engagement_fingerprint,
                    comments_fingerprint,
                    platform,
                    post_id,
                ))

        first_detail = existing is None or existing["detail_fingerprint"] is None
        return {
            "first_detail": first_detail,
            "content_changed": (
                first_detail
                or existing["content_fingerprint"] != content_fingerprint
            ),
            "media_changed": (
                first_detail
                or existing["media_fingerprint"] != media_fingerprint
            ),
            "engagement_changed": (
                first_detail
                or existing["engagement_fingerprint"]
                != engagement_fingerprint
            ),
            "comments_changed": (
                first_detail
                or existing["comments_fingerprint"]
                != comments_fingerprint
            ),
            "any_changed": (
                first_detail
                or existing["detail_fingerprint"] != detail_fingerprint
            ),
        }

    def get_access_context(
        self,
        *,
        platform: str,
        post_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT post_id, reported_comment_count,
                           platform_context_json, detail_raw_json
                    FROM posts
                    WHERE platform=%s AND post_id=%s
                """, (platform, post_id))
                row = cursor.fetchone()

        if row is None:
            return None
        return {
            "post_id": row["post_id"],
            "reported_comment_count": row["reported_comment_count"],
            "has_detail": row["detail_raw_json"] is not None,
            "platform_context": row["platform_context_json"] or {},
        }

    def update_comment_progress(
        self,
        *,
        platform: str,
        post_id: str,
        downloaded_comment_count: int,
        comment_status: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE posts
                    SET downloaded_comment_count=%s,
                        comment_status=%s,
                        updated_at=NOW()
                    WHERE platform=%s AND post_id=%s
                """, (
                    downloaded_comment_count,
                    comment_status,
                    platform,
                    post_id,
                ))

    def list_for_creator(
        self,
        *,
        platform: str,
        creator_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT post_id, detail_raw_json, comment_status
                    FROM posts
                    WHERE platform=%s AND creator_id=%s
                    ORDER BY id ASC
                    LIMIT %s
                """, (platform, creator_id, limit))
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def count_for_creator(
        self,
        *,
        platform: str,
        creator_id: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM posts
                    WHERE platform=%s AND creator_id=%s
                """, (platform, creator_id))
                row = cursor.fetchone()
        return int(row["count"])
