from app.platforms.xiaohongshu.normalizers import normalize_post_detail


def test_normalize_post_detail() -> None:
    raw = {
        "items": [
            {
                "note_card": {
                    "title": "Title",
                    "desc": "Body",
                    "type": "normal",
                    "time": 1700000000000,
                    "interact_info": {
                        "liked_count": "12",
                        "collected_count": "7",
                        "comment_count": "4",
                        "share_count": "2",
                    },
                }
            }
        ]
    }

    result = normalize_post_detail(raw, "note-1")

    assert result["post_id"] == "note-1"
    assert result["content"] == "Body"
    assert result["like_count"] == 12
    assert result["reported_comment_count"] == 4
