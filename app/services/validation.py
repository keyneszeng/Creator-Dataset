from dataclasses import dataclass
from typing import Any

from app.repositories.factory import create_validation_repository


@dataclass(frozen=True, slots=True)
class ValidationResult:
    post_id: str
    complete: bool
    issues: list[str]


class ValidationService:
    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository or create_validation_repository()

    def validate_post(
        self,
        post_id: str,
        *,
        require_comments: bool = True,
        require_media: bool = True,
        require_ocr: bool = True,
        require_stt: bool = True,
    ) -> ValidationResult:
        state = self.repository.inspect_post(post_id=post_id)
        if state is None:
            return ValidationResult(
                post_id=post_id,
                complete=False,
                issues=["post_not_found"],
            )

        issues: list[str] = []

        if not state["has_detail"]:
            issues.append("post_detail_missing")

        if require_comments and state["comment_status"] != "COMPLETE":
            issues.append(
                f"comments_{str(state['comment_status'] or 'missing').lower()}"
            )

        if require_media and state["media_incomplete"] > 0:
            issues.append(
                f"media_incomplete:{state['media_incomplete']}"
            )

        if require_ocr and state["ocr_incomplete"] > 0:
            issues.append(
                f"ocr_incomplete:{state['ocr_incomplete']}"
            )

        if require_stt and state["stt_incomplete"] > 0:
            issues.append(
                f"stt_incomplete:{state['stt_incomplete']}"
            )

        return ValidationResult(
            post_id=post_id,
            complete=not issues,
            issues=issues,
        )
