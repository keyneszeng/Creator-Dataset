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
               reply_count: int, pictures: list[Any], raw: dict[str, Any]) -> None:
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
