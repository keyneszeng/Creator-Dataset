from app.platforms.xiaohongshu.normalizers import (
    normalize_creator,
    normalize_posts_page,
)


def test_normalize_creator() -> None:
    raw = {
        "basic_info": {
            "nickname": "Alice",
            "desc": "hello",
            "imageb": "https://example.test/avatar.jpg",
        },
        "interactions": [
            {"type": "fans", "count": "123"},
            {"type": "follows", "count": "9"},
        ],
    }
    result = normalize_creator(raw, "creator-1")

    assert result["name"] == "Alice"
    assert result["follower_count"] == 123
    assert result["following_count"] == 9


def test_normalize_posts_page() -> None:
    raw = {
        "notes": [
            {
                "note_id": "note-1",
                "display_title": "First",
                "type": "normal",
            }
        ],
        "cursor": "next",
        "has_more": True,
    }
    result = normalize_posts_page(raw)

    assert result["has_more"] is True
    assert result["cursor"] == "next"
    assert result["notes"][0]["post_id"] == "note-1"
