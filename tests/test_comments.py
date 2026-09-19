from app.platforms.xiaohongshu.comments import normalize_comment_page


def test_root_comment_normalization() -> None:
    raw = {
        "comments": [
            {
                "id": "c1",
                "content": "hello",
                "like_count": "12",
                "sub_comment_count": "2",
                "sub_comment_has_more": True,
                "user_info": {
                    "user_id": "u1",
                    "nickname": "Alice",
                },
            }
        ],
        "cursor": "next",
        "has_more": True,
    }

    page = normalize_comment_page(raw, post_id="p1")
    comment = page["comments"][0]

    assert comment["comment_id"] == "c1"
    assert comment["root_comment_id"] == "c1"
    assert comment["parent_comment_id"] is None
    assert comment["depth"] == 0
    assert comment["reply_count"] == 2


def test_reply_normalization() -> None:
    raw = {
        "comments": [
            {
                "id": "c2",
                "content": "reply",
                "target_comment_id": "c1",
            }
        ],
        "cursor": "",
        "has_more": False,
    }

    page = normalize_comment_page(
        raw,
        post_id="p1",
        root_comment_id="c1",
    )
    reply = page["comments"][0]

    assert reply["root_comment_id"] == "c1"
    assert reply["parent_comment_id"] == "c1"
    assert reply["depth"] == 1
