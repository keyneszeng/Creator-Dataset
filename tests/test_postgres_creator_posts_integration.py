import os

import pytest

from app.postgres.creator_posts import (
    PostgresCreatorRepository,
    PostgresPostRepository,
)


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def _repos():
    creators = PostgresCreatorRepository(str(DATABASE_URL))
    posts = PostgresPostRepository(str(DATABASE_URL))
    creators.init_schema()
    return creators, posts


def _reset(posts: PostgresPostRepository) -> None:
    with posts._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE posts, creators RESTART IDENTITY CASCADE"
            )


def test_discovery_states_and_count() -> None:
    creators, posts = _repos()
    _reset(posts)

    creators.upsert(
        platform="xiaohongshu",
        creator_id="creator-1",
        profile_url="https://example.test/creator-1",
        name="Creator",
        avatar_url=None,
        bio="bio",
        follower_count=10,
        following_count=2,
        raw={"id": "creator-1"},
    )

    first = posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="First",
        post_type="normal",
        raw={"title": "First"},
        platform_context={"xsec_token": "a"},
    )
    unchanged = posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="First",
        post_type="normal",
        raw={"title": "First"},
        platform_context={"xsec_token": "a"},
    )
    changed = posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="Second",
        post_type="normal",
        raw={"title": "Second"},
        platform_context={"xsec_token": "b"},
    )

    assert first == "NEW"
    assert unchanged == "UNCHANGED"
    assert changed == "CHANGED"
    assert posts.count_for_creator(
        platform="xiaohongshu",
        creator_id="creator-1",
    ) == 1


def test_detail_change_classification() -> None:
    _, posts = _repos()
    _reset(posts)

    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url=None,
        title="Title",
        post_type="video",
        raw={},
        platform_context={},
    )

    first = posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="Body",
        post_type="video",
        published_at=1_700_000_000,
        like_count=10,
        favorite_count=2,
        share_count=1,
        reported_comment_count=3,
        raw={"v": 1},
        media=[{"media_type": "video", "remote_url": "https://a"}],
    )
    engagement = posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="Body",
        post_type="video",
        published_at=1_700_000_000,
        like_count=11,
        favorite_count=2,
        share_count=1,
        reported_comment_count=3,
        raw={"v": 2},
        media=[{"media_type": "video", "remote_url": "https://a"}],
    )
    comments = posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Title",
        content="Body",
        post_type="video",
        published_at=1_700_000_000,
        like_count=11,
        favorite_count=2,
        share_count=1,
        reported_comment_count=4,
        raw={"v": 3},
        media=[{"media_type": "video", "remote_url": "https://a"}],
    )

    assert first["first_detail"] is True
    assert engagement["engagement_changed"] is True
    assert engagement["content_changed"] is False
    assert engagement["media_changed"] is False
    assert engagement["comments_changed"] is False
    assert comments["comments_changed"] is True


def test_comment_progress_and_access_context() -> None:
    _, posts = _repos()
    _reset(posts)

    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url=None,
        title="Title",
        post_type="normal",
        raw={},
        platform_context={"xsec_token": "token"},
    )
    posts.update_comment_progress(
        platform="xiaohongshu",
        post_id="post-1",
        downloaded_comment_count=8,
        comment_status="COMPLETE",
    )

    rows = posts.list_for_creator(
        platform="xiaohongshu",
        creator_id="creator-1",
    )
    context = posts.get_access_context(
        platform="xiaohongshu",
        post_id="post-1",
    )

    assert rows[0]["comment_status"] == "COMPLETE"
    assert context["platform_context"]["xsec_token"] == "token"
