import json
from typing import Any

from app.core.database import db_session


class CreatorRepository:
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
        with db_session() as connection:
            connection.execute(
                """
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
                """,
                (
                    platform,
                    creator_id,
                    profile_url,
                    name,
                    avatar_url,
                    bio,
                    follower_count,
                    following_count,
                    json.dumps(raw, ensure_ascii=False),
                ),
            )

    def set_discovered_post_count(
        self, *, platform: str, creator_id: str, count: int
    ) -> None:
        with db_session() as connection:
            connection.execute(
                """
                UPDATE creators
                SET discovered_post_count=?, updated_at=CURRENT_TIMESTAMP
                WHERE platform=? AND creator_id=?
                """,
                (count, platform, creator_id),
            )


class PostRepository:
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
    ) -> None:
        with db_session() as connection:
            connection.execute(
                """
                INSERT INTO posts (
                    platform, creator_id, post_id, source_url, title,
                    post_type, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, post_id) DO UPDATE SET
                    creator_id=excluded.creator_id,
                    source_url=COALESCE(excluded.source_url, posts.source_url),
                    title=COALESCE(excluded.title, posts.title),
                    post_type=COALESCE(excluded.post_type, posts.post_type),
                    raw_json=excluded.raw_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    platform,
                    creator_id,
                    post_id,
                    source_url,
                    title,
                    post_type,
                    json.dumps(raw, ensure_ascii=False),
                ),
            )

    def count_for_creator(self, *, platform: str, creator_id: str) -> int:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM posts
                WHERE platform=? AND creator_id=?
                """,
                (platform, creator_id),
            ).fetchone()
        return int(row["count"])
