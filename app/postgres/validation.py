from typing import Any

from app.postgres.content import _PostgresContentBase


class PostgresValidationRepository(_PostgresContentBase):
    def inspect_post(self, *, post_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT detail_raw_json, comment_status "
                    "FROM posts WHERE post_id=%s",
                    (post_id,),
                )
                post = cursor.fetchone()
                if post is None:
                    return None

                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM media
                    WHERE post_id=%s AND is_active=TRUE
                      AND download_status!='COMPLETE'
                """, (post_id,))
                media_failed = cursor.fetchone()["count"]

                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM media m
                    WHERE m.post_id=%s AND m.is_active=TRUE
                      AND m.media_type=ANY(%s)
                      AND m.download_status='COMPLETE'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM ocr_results o
                          WHERE o.media_id=m.id
                            AND o.status='COMPLETE'
                      )
                """, (
                    post_id,
                    ["image", "cover", "comment_image"],
                ))
                missing_ocr = cursor.fetchone()["count"]

                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM media m
                    WHERE m.post_id=%s AND m.is_active=TRUE
                      AND m.media_type='video'
                      AND m.download_status='COMPLETE'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM transcripts t
                          WHERE t.media_id=m.id
                            AND t.status='COMPLETE'
                      )
                """, (post_id,))
                missing_stt = cursor.fetchone()["count"]

        return {
            "has_detail": post["detail_raw_json"] is not None,
            "comment_status": post["comment_status"],
            "media_incomplete": int(media_failed or 0),
            "ocr_incomplete": int(missing_ocr or 0),
            "stt_incomplete": int(missing_stt or 0),
        }
