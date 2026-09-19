import os

import pytest

from app.postgres.content import (
    PostgresCheckpointRepository,
    PostgresCommentRepository,
    PostgresMediaRepository,
    PostgresOcrRepository,
    PostgresTextUnitRepository,
    PostgresTranscriptRepository,
)


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def _init():
    comments = PostgresCommentRepository(str(DATABASE_URL))
    comments.init_schema()
    return comments


def _reset(repository) -> None:
    with repository._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE text_units, transcripts, ocr_results, "
                "comments, media, checkpoints, crawl_audits "
                "RESTART IDENTITY CASCADE"
            )


def test_comments_register_comment_images_and_counts() -> None:
    comments = _init()
    _reset(comments)

    comments.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id="c1",
        root_comment_id="c1",
        parent_comment_id=None,
        user_id="u1",
        user_name="Alice",
        user_avatar=None,
        content="root",
        like_count=3,
        ip_location=None,
        published_at=1_700_000_000,
        depth=0,
        has_more_replies=True,
        reply_count=1,
        pictures=[],
        picture_urls=["https://example.test/comment.jpg"],
        raw={"id": "c1"},
    )
    comments.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id="r1",
        root_comment_id="c1",
        parent_comment_id="c1",
        user_id="u2",
        user_name="Bob",
        user_avatar=None,
        content="reply",
        like_count=1,
        ip_location=None,
        published_at=1_700_000_001,
        depth=1,
        has_more_replies=False,
        reply_count=0,
        pictures=[],
        picture_urls=[],
        raw={"id": "r1"},
    )

    counts = comments.counts_for_post(
        platform="xiaohongshu",
        post_id="post-1",
    )
    roots = comments.list_roots_with_replies(
        platform="xiaohongshu",
        post_id="post-1",
    )

    assert counts == {"total": 2, "root": 1, "reply": 1}
    assert roots[0]["comment_id"] == "c1"

    with comments._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT media_type FROM media WHERE comment_id=%s",
                ("c1",),
            )
            row = cursor.fetchone()
    assert row["media_type"] == "comment_image"


def test_checkpoint_reset_and_finished_prefix() -> None:
    checkpoints = PostgresCheckpointRepository(str(DATABASE_URL))
    checkpoints.init_schema()
    _reset(checkpoints)

    checkpoints.save(
        platform="xiaohongshu",
        scope="root_comments",
        object_id="post-1",
        cursor="done",
        finished=True,
        metadata={"page": 1},
    )
    checkpoints.save(
        platform="xiaohongshu",
        scope="sub_comments",
        object_id="post-1:c1",
        cursor="done",
        finished=True,
    )

    assert checkpoints.count_finished_prefix(
        platform="xiaohongshu",
        scope="sub_comments",
        object_id_prefix="post-1:",
    ) == 1

    assert checkpoints.reset_comment_crawl(
        platform="xiaohongshu",
        post_id="post-1",
    ) == 2


def test_media_reconciliation_and_derived_results() -> None:
    media = PostgresMediaRepository(str(DATABASE_URL))
    media.init_schema()
    _reset(media)

    old_id = media.upsert(
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_type="image",
        remote_url="https://example.test/old.jpg",
    )
    media.reconcile_post_media(
        platform="xiaohongshu",
        post_id="post-1",
        media_items=[
            {
                "media_type": "image",
                "remote_url": "https://example.test/new.jpg",
            }
        ],
    )

    with media._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_active FROM media WHERE id=%s",
                (old_id,),
            )
            assert cursor.fetchone()["is_active"] is False
            cursor.execute(
                "SELECT id FROM media WHERE post_id=%s AND is_active=TRUE",
                ("post-1",),
            )
            active_id = int(cursor.fetchone()["id"])

    media.mark_downloaded(
        media_id=active_id,
        local_path=None,
        storage_backend="s3",
        storage_key="posts/post-1/new.jpg",
        sha256="abc",
    )

    ocr = PostgresOcrRepository(str(DATABASE_URL))
    ocr.save_result(
        media_id=active_id,
        engine="fake",
        engine_version="1",
        language="ch",
        full_text="图片文字",
        average_confidence=0.99,
        blocks=[],
    )
    assert ocr.exists(media_id=active_id, engine="fake") is True

    transcript = PostgresTranscriptRepository(str(DATABASE_URL))
    transcript.save_result(
        media_id=active_id,
        engine="fake-stt",
        engine_version="1",
        model="m",
        language="zh",
        language_probability=0.98,
        full_text="视频文字",
        segments=[],
    )
    assert transcript.exists(
        media_id=active_id,
        engine="fake-stt",
        model="m",
    ) is True

    units = PostgresTextUnitRepository(str(DATABASE_URL))
    units.upsert(
        source_key="media:1:ocr",
        platform="xiaohongshu",
        post_id="post-1",
        comment_id=None,
        media_id=active_id,
        unit_type="image_ocr",
        text="图片文字",
        confidence=0.99,
        provenance="ocr",
    )
    assert units.list_for_post(post_id="post-1")[0]["text"] == "图片文字"
