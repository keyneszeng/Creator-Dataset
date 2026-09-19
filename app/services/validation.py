from dataclasses import dataclass

from app.core.database import db_session


@dataclass(frozen=True, slots=True)
class ValidationResult:
    post_id: str
    complete: bool
    issues: list[str]


class ValidationService:
    def validate_post(
        self,
        post_id: str,
        *,
        require_comments: bool = True,
        require_media: bool = True,
        require_ocr: bool = True,
        require_stt: bool = True,
    ) -> ValidationResult:
        issues: list[str] = []

        with db_session() as connection:
            post = connection.execute(
                "SELECT * FROM posts WHERE post_id=?",
                (post_id,),
            ).fetchone()
            if post is None:
                return ValidationResult(
                    post_id=post_id,
                    complete=False,
                    issues=["post_not_found"],
                )

            if post["detail_raw_json"] is None:
                issues.append("post_detail_missing")

            if require_comments and post["comment_status"] != "COMPLETE":
                issues.append(
                    f"comments_{str(post['comment_status'] or 'missing').lower()}"
                )

            if require_media:
                media_failed = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM media
                    WHERE post_id=? AND download_status!='COMPLETE'
                    """,
                    (post_id,),
                ).fetchone()["count"]
                if int(media_failed or 0) > 0:
                    issues.append(f"media_incomplete:{int(media_failed)}")

            if require_ocr:
                missing_ocr = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM media m
                    WHERE m.post_id=?
                      AND m.media_type IN ('image', 'cover', 'comment_image')
                      AND m.download_status='COMPLETE'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM ocr_results o
                          WHERE o.media_id=m.id AND o.status='COMPLETE'
                      )
                    """,
                    (post_id,),
                ).fetchone()["count"]
                if int(missing_ocr or 0) > 0:
                    issues.append(f"ocr_incomplete:{int(missing_ocr)}")

            if require_stt:
                missing_stt = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM media m
                    WHERE m.post_id=?
                      AND m.media_type='video'
                      AND m.download_status='COMPLETE'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM transcripts t
                          WHERE t.media_id=m.id AND t.status='COMPLETE'
                      )
                    """,
                    (post_id,),
                ).fetchone()["count"]
                if int(missing_stt or 0) > 0:
                    issues.append(f"stt_incomplete:{int(missing_stt)}")

        return ValidationResult(
            post_id=post_id,
            complete=not issues,
            issues=issues,
        )
