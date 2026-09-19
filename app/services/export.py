import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.repositories.factory import create_export_repository, create_text_unit_repository
from app.core.versioning import DATASET_SCHEMA_VERSION, PIPELINE_API_VERSION
from app.services.analysis_corpus import AnalysisCorpusService
from app.storage.base import ObjectStore, StoredObject
from app.storage.factory import create_object_store


def _loads(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


class ExportService:
    def __init__(
        self,
        repository: Any | None = None,
        text_units: Any | None = None,
        object_store: ObjectStore | None = None,
    ) -> None:
        self.repository = repository or create_export_repository()
        self.text_units = text_units or create_text_unit_repository()
        self.object_store = object_store or create_object_store()

    def export_post(self, post_id: str) -> dict[str, str]:
        bundle = self.repository.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")

        AnalysisCorpusService(
            export_repository=self.repository,
            text_units=self.text_units,
        ).rebuild_post(post_id)

        post = self._normalize_row(bundle["post"])
        comments = [self._normalize_row(row) for row in bundle["comments"]]
        media = [self._normalize_media(row) for row in bundle["media"]]
        text_units = self.text_units.list_for_post(post_id=post_id)

        prefix = f"xiaohongshu/posts/{post_id}/export"

        with tempfile.TemporaryDirectory(
            prefix=f"creator-dataset-export-{post_id}-"
        ) as temp_dir:
            export_dir = Path(temp_dir)

            post_path = export_dir / "post.json"
            comments_path = export_dir / "comments.jsonl"
            media_path = export_dir / "media.jsonl"
            analysis_path = export_dir / "analysis.jsonl"
            markdown_path = export_dir / "knowledge.md"
            manifest_path = export_dir / "manifest.json"

            post_path.write_text(
                json.dumps(post, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            comments_path.write_text(
                "".join(
                    json.dumps(comment, ensure_ascii=False, default=str) + "\n"
                    for comment in comments
                ),
                encoding="utf-8",
            )
            media_path.write_text(
                "".join(
                    json.dumps(item, ensure_ascii=False, default=str) + "\n"
                    for item in media
                ),
                encoding="utf-8",
            )
            analysis_path.write_text(
                "".join(
                    json.dumps(item, ensure_ascii=False, default=str) + "\n"
                    for item in text_units
                ),
                encoding="utf-8",
            )
            markdown_path.write_text(
                self._build_markdown(post, comments, media),
                encoding="utf-8",
            )

            files = {
                "post.json": post_path,
                "comments.jsonl": comments_path,
                "media.jsonl": media_path,
                "analysis.jsonl": analysis_path,
                "knowledge.md": markdown_path,
            }
            manifest = {
                "dataset_schema_version": DATASET_SCHEMA_VERSION,
                "pipeline_api_version": PIPELINE_API_VERSION,
                "platform": post.get("platform"),
                "post_id": post_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "storage_backend": self.object_store.name,
                "export_prefix": prefix,
                "files": {
                    name: {
                        "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(
                            path.read_bytes()
                        ).hexdigest(),
                        "storage_key": f"{prefix}/{name}",
                    }
                    for name, path in files.items()
                },
            }
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            files["manifest.json"] = manifest_path

            stored = {
                name: self.object_store.put_file(
                    path,
                    key=f"{prefix}/{name}",
                )
                for name, path in files.items()
            }

        return {
            "post_json": self._reference(stored["post.json"]),
            "comments_jsonl": self._reference(stored["comments.jsonl"]),
            "media_jsonl": self._reference(stored["media.jsonl"]),
            "analysis_jsonl": self._reference(stored["analysis.jsonl"]),
            "knowledge_markdown": self._reference(stored["knowledge.md"]),
            "manifest_json": self._reference(stored["manifest.json"]),
            "export_prefix": prefix,
            "storage_backend": self.object_store.name,
        }

    def _reference(self, stored: StoredObject) -> str:
        if stored.local_path:
            return stored.local_path
        return f"{stored.backend}://{stored.key}"

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
        data["transcript_segments"] = _loads(
            data.pop("transcript_segments_json", None)
        )
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

        video_transcripts = [
            item for item in media
            if item.get("media_type") == "video" and item.get("transcript_text")
        ]
        if video_transcripts:
            lines.extend(["## Video Transcript", ""])
            for item in video_transcripts:
                language = item.get("transcript_language") or "unknown"
                probability = item.get("transcript_language_probability")
                probability_text = (
                    f"{float(probability):.3f}"
                    if probability is not None
                    else "unknown"
                )
                lines.extend([
                    f"### Media {item['id']} ({item.get('transcript_model') or 'model'})",
                    "",
                    f"Detected language: {language} ({probability_text})",
                    "",
                    str(item["transcript_text"]),
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
            "Video transcripts are derived from source media and remain linked to media_id.",
            "Original platform text, OCR-derived text, and STT-derived text are intentionally kept separate.",
            "",
        ])
        return "\n".join(lines)
