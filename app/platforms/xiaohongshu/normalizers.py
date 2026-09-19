from typing import Any


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_creator(raw: dict[str, Any], creator_id: str) -> dict[str, Any]:
    basic = raw.get("basic_info") if isinstance(raw.get("basic_info"), dict) else {}
    interactions = (
        raw.get("interactions")
        if isinstance(raw.get("interactions"), list)
        else []
    )

    metrics: dict[str, int | None] = {
        "followers": None,
        "following": None,
    }
    for item in interactions:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").lower()
        count = item.get("count")
        try:
            normalized_count = int(count) if count is not None else None
        except (TypeError, ValueError):
            normalized_count = None
        if item_type in {"fans", "followers", "follower"}:
            metrics["followers"] = normalized_count
        elif item_type in {"follows", "following", "follow"}:
            metrics["following"] = normalized_count

    return {
        "creator_id": creator_id,
        "name": _first(basic, "nickname", "name", "user_name")
        or _first(raw, "nickname", "name", "user_name"),
        "avatar_url": _first(basic, "imageb", "images", "avatar")
        or _first(raw, "avatar", "imageb"),
        "bio": _first(basic, "desc", "description", "bio")
        or _first(raw, "desc", "description", "bio"),
        "follower_count": metrics["followers"],
        "following_count": metrics["following"],
    }


def normalize_posts_page(raw: dict[str, Any]) -> dict[str, Any]:
    notes = raw.get("notes")
    if not isinstance(notes, list):
        notes = raw.get("items")
    if not isinstance(notes, list):
        notes = []

    has_more = bool(raw.get("has_more"))
    cursor = str(raw.get("cursor") or "")

    normalized_notes: list[dict[str, Any]] = []
    for item in notes:
        if not isinstance(item, dict):
            continue
        note_id = _first(item, "note_id", "id")
        if not note_id and isinstance(item.get("note_card"), dict):
            note_id = _first(item["note_card"], "note_id", "id")
        if not note_id:
            continue

        card = item.get("note_card") if isinstance(item.get("note_card"), dict) else item
        title = _first(card, "display_title", "title", "name")
        note_type = _first(card, "type", "note_type")
        xsec_token = _first(item, "xsec_token") or _first(card, "xsec_token")

        normalized_notes.append(
            {
                "post_id": str(note_id),
                "title": str(title) if title is not None else None,
                "post_type": str(note_type) if note_type is not None else None,
                "xsec_token": str(xsec_token) if xsec_token is not None else None,
                "raw": item,
            }
        )

    return {
        "notes": normalized_notes,
        "cursor": cursor,
        "has_more": has_more,
    }
