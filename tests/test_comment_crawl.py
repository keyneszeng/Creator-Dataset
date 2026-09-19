from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import PostRepository
from app.services.comment_crawl import CommentCrawlService


class FakeGateway:
    def get_comments_page(
        self,
        post_id: str,
        cursor: str = "",
        xsec_token: str = "",
        xsec_source: str = "pc_feed",
    ):
        assert xsec_token == "token-1"
        if not cursor:
            return {
                "comments": [
                    {
                        "id": "c1",
                        "content": "root-1",
                        "sub_comment_count": "2",
                        "sub_comment_has_more": True,
                    },
                    {
                        "id": "c2",
                        "content": "root-2",
                        "sub_comment_count": "0",
                    },
                ],
                "cursor": "",
                "has_more": False,
            }
        raise AssertionError("unexpected root cursor")

    def get_sub_comments_page(
        self,
        post_id: str,
        root_comment_id: str,
        cursor: str = "",
    ):
        assert root_comment_id == "c1"
        return {
            "comments": [
                {
                    "id": "r1",
                    "content": "reply-1",
                    "target_comment_id": "c1",
                },
                {
                    "id": "r2",
                    "content": "reply-2",
                    "target_comment_id": "c1",
                },
            ],
            "cursor": "",
            "has_more": False,
        }


@pytest.mark.asyncio
async def test_comment_crawl_and_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "comments.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://www.xiaohongshu.com/explore/post-1",
        title="Post",
        post_type="normal",
        raw={"note_id": "post-1"},
        platform_context={
            "xsec_token": "token-1",
            "xsec_source": "pc_feed",
        },
    )
    posts.update_detail(
        platform="xiaohongshu",
        post_id="post-1",
        title="Post",
        content="Body",
        post_type="normal",
        published_at=1700000000000,
        like_count=1,
        favorite_count=2,
        share_count=3,
        reported_comment_count=4,
        raw={"items": []},
    )

    service = CommentCrawlService(
        gateway=FakeGateway(),
        posts=posts,
    )
    result = await service.crawl_post("post-1")

    assert result.root_comments == 2
    assert result.reply_comments == 2
    assert result.failed_threads == 0
    assert result.status == "COMPLETE"
    assert result.completeness_ratio == 1.0

    with database.db_session(db_path) as connection:
        rows = connection.execute(
            "SELECT comment_id, root_comment_id, parent_comment_id, depth "
            "FROM comments ORDER BY id"
        ).fetchall()
        audit = connection.execute(
            "SELECT * FROM crawl_audits WHERE post_id='post-1' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert len(rows) == 4
    assert rows[2]["root_comment_id"] == "c1"
    assert rows[2]["parent_comment_id"] == "c1"
    assert rows[2]["depth"] == 1
    assert audit["actual_comments"] == 4
    assert audit["pagination_finished"] == 1
