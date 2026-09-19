from typing import Any


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_comment(
    raw: dict[str, Any],
    *,
    post_id: str,
    root_comment_id: str | None = None,
) -> dict[str, Any] | None:
    comment_id = _first(raw, "id", "comment_id")
    if not comment_id:
        return None

    user = raw.get("user_info") if isinstance(raw.get("user_info"), dict) else {}
    pictures = raw.get("pictures")
    if not isinstance(pictures, list):
        pictures = raw.get("image_list")
    if not isinstance(pictures, list):
        pictures = []

    is_root = root_comment_id is None
    root_id = str(comment_id) if is_root else str(root_comment_id)

    parent_id = _first(raw, "target_comment_id", "parent_comment_id")
    if not parent_id and not is_root:
        parent_id = root_id

    return {
        "post_id": post_id,
        "comment_id": str(comment_id),
        "root_comment_id": root_id,
        "parent_comment_id": str(parent_id) if parent_id else None,
        "user_id": _first(user, "user_id", "id"),
        "user_name": _first(user, "nickname", "name"),
        "user_avatar": _first(user, "image", "avatar"),
        "content": _first(raw, "content", "text"),
        "like_count": _to_int(_first(raw, "like_count", "liked_count")),
        "ip_location": _first(raw, "ip_location", "ipLocation"),
        "published_at": _first(raw, "create_time", "time", "timestamp"),
        "depth": 0 if is_root else 1,
        "has_more_replies": bool(
            _first(raw, "sub_comment_has_more", "has_more_replies") or False
        ),
        "reply_count": _to_int(
            _first(raw, "sub_comment_count", "reply_count")
        ) or 0,
        "pictures": pictures,
        "raw": raw,
    }


def normalize_comment_page(
    raw: dict[str, Any],
    *,
    post_id: str,
    root_comment_id: str | None = None,
) -> dict[str, Any]:
    comments = raw.get("comments")
    if not isinstance(comments, list):
        comments = []

    normalized = []
    for item in comments:
        if not isinstance(item, dict):
            continue
        comment = normalize_comment(
            item,
            post_id=post_id,
            root_comment_id=root_comment_id,
        )
        if comment is not None:
            normalized.append(comment)

    return {
        "comments": normalized,
        "cursor": str(raw.get("cursor") or ""),
        "has_more": bool(raw.get("has_more")),
    }
