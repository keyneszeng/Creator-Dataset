from typing import Any

from app.core.database import db_session


class SqliteValidationRepository:
    def inspect_post(self, *, post_id: str) -> dict[str, Any] | None:
        with db_session() as connection:
            post = connection.execute(
                "SELECT detail_raw_json, comment_status "
                "FROM posts WHERE post_id=?",
                (post_id,),
            ).fetchone()
            if post is None:
                return None

            media_failed = connection.execute("""
                SELECT COUNT(*) AS count
                FROM media
                WHERE post_id=? AND is_active=1
                  AND download_status!='COMPLETE'
            """, (post_id,)).fetchone()["count"]

            missing_ocr = connection.execute("""
                SELECT COUNT(*) AS count
                FROM media m
                WHERE m.post_id=? AND m.is_active=1
                  AND m.media_type IN (
                      'image', 'cover', 'comment_image'
                  )
                  AND m.download_status='COMPLETE'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ocr_results o
                      WHERE o.media_id=m.id AND o.status='COMPLETE'
                  )
            """, (post_id,)).fetchone()["count"]

            missing_stt = connection.execute("""
                SELECT COUNT(*) AS count
                FROM media m
                WHERE m.post_id=? AND m.is_active=1
                  AND m.media_type='video'
                  AND m.download_status='COMPLETE'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM transcripts t
                      WHERE t.media_id=m.id AND t.status='COMPLETE'
                  )
            """, (post_id,)).fetchone()["count"]

        return {
            "has_detail": post["detail_raw_json"] is not None,
            "comment_status": post["comment_status"],
            "media_incomplete": int(media_failed or 0),
            "ocr_incomplete": int(missing_ocr or 0),
            "stt_incomplete": int(missing_stt or 0),
        }
