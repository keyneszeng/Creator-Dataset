from typing import Any

from app.repositories.factory import (
    create_export_repository,
    create_llm_repository,
)
from app.llm.models import SimplifiedDatasetResult


def _excerpt(value: str, limit: int = 1000) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class SimpleDatasetViewService:
    def __init__(
        self,
        *,
        export_repository: Any | None = None,
        llm_repository: Any | None = None,
    ) -> None:
        self.exports = export_repository or create_export_repository()
        self.llm = llm_repository or create_llm_repository()

    def build(
        self,
        *,
        user_id: int,
        post_id: str,
    ) -> dict[str, Any]:
        bundle = self.exports.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")

        post = bundle["post"]
        comments = bundle["comments"]
        title = str(post.get("title") or "").strip()
        author_text = str(post.get("content") or "").strip()

        result = SimplifiedDatasetResult(
            title=title,
            summary=_excerpt(author_text),
            key_points=[],
            topics=[],
            useful_facts=[],
            audience_questions=[],
            comment_insights=[],
            action_items=[],
            caveats=[],
            language=None,
        ).model_dump()

        latest = self.llm.latest_for_post(
            user_id=user_id,
            post_id=post_id,
        )
        organized_by_ai = False
        ai_run_id = None
        ai_status = None

        if latest is not None:
            ai_run_id = int(latest["id"])
            ai_status = str(latest["status"])
            if latest["status"] == "COMPLETE" and latest.get("result"):
                result = SimplifiedDatasetResult.model_validate(
                    latest["result"]
                ).model_dump()
                organized_by_ai = True

        return {
            **result,
            "post_id": post_id,
            "published_at": post.get("published_at"),
            "source_url": post.get("source_url"),
            "metrics": {
                "likes": post.get("like_count"),
                "favorites": post.get("favorite_count"),
                "shares": post.get("share_count"),
                "comments": post.get("reported_comment_count"),
            },
            "comment_count_loaded": len(comments),
            "organized_by_ai": organized_by_ai,
            "ai_run_id": ai_run_id,
            "ai_status": ai_status,
        }
