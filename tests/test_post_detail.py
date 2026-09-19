from pathlib import Path

import pytest

from app.core import database
from app.core.repositories import PostRepository
from app.services.post_detail import PostDetailService


class FakeGateway:
    def get_post_detail(
        self,
        post_id: str,
        *,
        xsec_token: str = "",
        xsec_source: str = "pc_feed",
    ):
        assert xsec_token == "token-1"
        return {
            "items": [
                {
                    "note_card": {
                        "title": "Detailed title",
                        "desc": "Detailed body",
                        "type": "normal",
                        "time": 1700000000000,
                        "interact_info": {
                            "liked_count": "100",
                            "collected_count": "50",
                            "comment_count": "10",
                            "share_count": "5",
                        },
                    }
                }
            ]
        }


@pytest.mark.asyncio
async def test_post_detail_enrichment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "creator.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="note-1",
        source_url="https://www.xiaohongshu.com/explore/note-1",
        title="Preview",
        post_type="normal",
        raw={"note_id": "note-1"},
        platform_context={
            "xsec_token": "token-1",
            "xsec_source": "pc_feed",
        },
    )

    service = PostDetailService(
        gateway=FakeGateway(),
        post_repository=posts,
    )
    result = await service.enrich_creator("creator-1")

    assert result.enriched == 1

    with database.db_session(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM posts WHERE post_id='note-1'"
        ).fetchone()

    assert row["title"] == "Detailed title"
    assert row["content"] == "Detailed body"
    assert row["like_count"] == 100
    assert row["favorite_count"] == 50
    assert row["reported_comment_count"] == 10
    assert row["detail_raw_json"] is not None
