from app.core.repositories import ExportRepository, TextUnitRepository


class AnalysisCorpusService:
    def __init__(
        self,
        *,
        export_repository: ExportRepository | None = None,
        text_units: TextUnitRepository | None = None,
    ) -> None:
        self.export_repository = export_repository or ExportRepository()
        self.text_units = text_units or TextUnitRepository()

    def rebuild_post(self, post_id: str) -> dict[str, int]:
        bundle = self.export_repository.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")

        post = bundle["post"]
        comments = bundle["comments"]
        media = bundle["media"]

        self.text_units.delete_for_post(post_id=post_id)
        created = 0

        author_text = str(post.get("content") or "").strip()
        if author_text:
            self.text_units.upsert(
                source_key=f"post:{post_id}:author",
                platform=str(post["platform"]),
                post_id=post_id,
                comment_id=None,
                media_id=None,
                unit_type="author_text",
                text=author_text,
                confidence=None,
                provenance="platform_text",
            )
            created += 1

        for item in media:
            ocr_text = str(item.get("ocr_text") or "").strip()
            if ocr_text:
                comment_id = item.get("comment_id")
                unit_type = (
                    "comment_image_ocr"
                    if comment_id
                    else "image_ocr"
                )
                self.text_units.upsert(
                    source_key=f"media:{item['id']}:ocr:{item.get('ocr_engine') or 'unknown'}",
                    platform=str(item["platform"]),
                    post_id=post_id,
                    comment_id=str(comment_id) if comment_id else None,
                    media_id=int(item["id"]),
                    unit_type=unit_type,
                    text=ocr_text,
                    confidence=item.get("ocr_confidence"),
                    provenance="ocr",
                )
                created += 1

            transcript_text = str(item.get("transcript_text") or "").strip()
            if transcript_text:
                self.text_units.upsert(
                    source_key=(
                        f"media:{item['id']}:stt:"
                        f"{item.get('transcript_engine') or 'unknown'}:"
                        f"{item.get('transcript_model') or 'unknown'}"
                    ),
                    platform=str(item["platform"]),
                    post_id=post_id,
                    comment_id=None,
                    media_id=int(item["id"]),
                    unit_type="video_transcript",
                    text=transcript_text,
                    confidence=item.get("transcript_language_probability"),
                    provenance="stt",
                )
                created += 1

        for comment in comments:
            text = str(comment.get("content") or "").strip()
            if not text:
                continue
            depth = int(comment.get("depth") or 0)
            unit_type = "comment" if depth == 0 else "reply"
            self.text_units.upsert(
                source_key=f"comment:{comment['comment_id']}:text",
                platform=str(comment["platform"]),
                post_id=post_id,
                comment_id=str(comment["comment_id"]),
                media_id=None,
                unit_type=unit_type,
                text=text,
                confidence=None,
                provenance="platform_text",
            )
            created += 1

        return {"text_units": created}
