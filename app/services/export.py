import json
from pathlib import Path
from typing import Any

from app.core.repositories import ExportRepository
from app.core.settings import get_settings


def _loads(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


class ExportService:
    def __init__(self, repository: ExportRepository | None = None) -> None:
        self.repository = repository or ExportRepository()

    def export_post(self, post_id: str) -> dict[str, str]:
        bundle = self.repository.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")

        settings = get_settings()
        export_dir = (
            settings.data_dir
            / "xiaohongshu"
            / "posts"
            / post_id
            / "export"
        )
        export_dir.mkdir(parents=True, exist_ok=True)

        post = self._normalize_row(bundle["post"])
        comments = [self._normalize_row(row) for row in bundle["comments"]]
        media = [self._normalize_media(row) for row in bundle["media"]]

        post_path = export_dir / "post.json"
        comments_path = export_dir / "comments.jsonl"
        media_path = export_dir / "media.jsonl"
        markdown_path = export_dir / "knowledge.md"

        post_path.write_text(
            json.dumps(post, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        comments_path.write_text(
            "".join(
                json.dumps(comment, ensure_ascii=False) + "\n"
                for comment in comments
            ),
            encoding="utf-8",
        )
        media_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False) + "\n"
                for item in media
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(
            self._build_markdown(post, comments, media),
            encoding="utf-8",
        )

        return {
            "post_json": str(post_path),
            "comments_jsonl": str(comments_path),
            "media_jsonl": str(media_path),
            "knowledge_markdown": str(markdown_path),
        }

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        for key in (
            "raw_json",
            "detail_raw_json",
            "platform_context_json",
        ):
            if key in data:
                data[key] = _loads(data[key])
        return data

    def _normalize_media(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["ocr_blocks"] = _loads(data.pop("ocr_blocks_json", None))
        return data

    def _build_markdown(
        self,
        post: dict[str, Any],
        comments: list[dict[str, Any]],
        media: list[dict[str, Any]],
    ) -> str:
        title = post.get("title") or post["post_id"]
        lines = [
            f"# {title}",
            "",
            f"- Post ID: {post['post_id']}",
            f"- Source: {post.get('source_url') or ''}",
            f"- Published at: {post.get('published_at') or ''}",
            "",
            "## Author Text",
            "",
            str(post.get("content") or ""),
            "",
        ]

        post_ocr = [
            item for item in media
            if not item.get("comment_id") and item.get("ocr_text")
        ]
        if post_ocr:
            lines.extend(["## Text Recognized From Post Images", ""])
            for item in post_ocr:
                confidence = item.get("ocr_confidence")
                confidence_text = (
                    f"{float(confidence):.3f}"
                    if confidence is not None
                    else "unknown"
                )
                lines.extend([
                    f"### Media {item['id']} ({item['media_type']})",
                    "",
                    f"OCR confidence: {confidence_text}",
                    "",
                    str(item["ocr_text"]),
                    "",
                ])

        media_by_comment: dict[str, list[dict[str, Any]]] = {}
        for item in media:
            comment_id = item.get("comment_id")
            if comment_id and item.get("ocr_text"):
                media_by_comment.setdefault(str(comment_id), []).append(item)

        if comments:
            lines.extend(["## Comments", ""])
            for comment in comments:
                indent = "  " * int(comment.get("depth") or 0)
                author = comment.get("user_name") or comment.get("user_id") or "unknown"
                lines.append(
                    f"{indent}- [{comment['comment_id']}] {author}: "
                    f"{comment.get('content') or ''}"
                )
                for item in media_by_comment.get(
                    str(comment["comment_id"]),
                    [],
                ):
                    ocr_text = str(item.get("ocr_text") or "").replace(
                        "\n",
                        " / ",
                    )
                    lines.append(
                        f"{indent}  - [OCR media:{item['id']}] {ocr_text}"
                    )
            lines.append("")

        lines.extend([
            "## Dataset Provenance",
            "",
            "OCR text is derived from source images and remains linked to media_id.",
            "Original post/comment text and OCR-derived text are intentionally kept separate.",
            "",
        ])
        return "\n".join(lines)
