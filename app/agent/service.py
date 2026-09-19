from typing import Any

from app.core.settings import get_settings
from app.core.versioning import DATASET_SCHEMA_VERSION
from app.repositories.factory import (
    create_dataset_artifact_repository,
    create_export_repository,
    create_job_repository,
    create_post_repository,
    create_saas_repository,
    create_text_unit_repository,
)
from app.saas.models import Principal, UserRole
from app.saas.service import SaasService
from app.services.queue import QueueService
from app.services.simple_view import SimpleDatasetViewService


class AgentAccessError(PermissionError):
    pass


class AgentService:
    """Compact product-facing facade for MCP/agent tools."""

    def __init__(self, principal: Principal | None = None) -> None:
        self.principal = principal or Principal(
            user_id=0,
            email="local-agent@localhost",
            role=UserRole.ADMIN,
        )
        self.access = create_saas_repository()
        self.posts = create_post_repository()
        self.jobs = create_job_repository()
        self.artifacts = create_dataset_artifact_repository()
        self.exports = create_export_repository()
        self.text_units = create_text_unit_repository()
        self.queue = QueueService()
        self.saas = SaasService(repository=self.access)

    def account_status(self) -> dict[str, Any]:
        settings = get_settings()
        if settings.agent_free_mode:
            return {
                "mode": "free",
                "role": self.principal.role.value,
                "unlimited": True,
            }

        account = self.saas.account(self.principal)
        credits = account["credits"]
        return {
            "mode": "commercial",
            "role": account["user"]["role"],
            "free_credits": credits.get("free", 0),
            "paid_credits": credits.get("paid", 0),
            "total_credits": credits.get("total", 0),
            "unlimited": bool(credits.get("unlimited", False)),
        }

    def creator_submit(
        self,
        url: str,
        *,
        max_pages: int = 20,
    ) -> dict[str, Any]:
        result = self.queue.enqueue_creator_import(
            url,
            max_pages=max_pages,
        )
        if self.principal.user_id != 0:
            self.access.record_creator_submission(
                user_id=self.principal.user_id,
                platform="xiaohongshu",
                creator_id=result.creator_id,
                submitted_url=url,
            )
        job = self.jobs.get(job_id=result.job_id)
        return {
            "creator_id": result.creator_id,
            "status": job["status"] if job else "PENDING",
            "import_job_id": result.job_id,
        }

    def creator_status(self, creator_id: str) -> dict[str, Any]:
        self._require_creator_access(creator_id)
        key = f"creator-import:v2:xiaohongshu:{creator_id}"
        job = self.jobs.get_by_idempotency_key(
            idempotency_key=key,
        )
        return {
            "creator_id": creator_id,
            "status": job["status"] if job else "NOT_STARTED",
            "discovered_posts": self.posts.count_for_creator(
                platform="xiaohongshu",
                creator_id=creator_id,
            ),
            "job_id": job["id"] if job else None,
            "error": job.get("last_error") if job else None,
        }

    def creator_posts(
        self,
        creator_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._require_creator_access(creator_id)
        limit = max(1, min(limit, 50))
        offset = max(0, offset)
        items = self.posts.list_catalog(
            platform="xiaohongshu",
            creator_id=creator_id,
            limit=limit,
            offset=offset,
        )
        post_ids = [str(item["post_id"]) for item in items]
        settings = get_settings()
        unlocked = (
            set(post_ids)
            if settings.agent_free_mode
            else self.access.entitled_post_ids(
                user_id=self.principal.user_id,
                platform="xiaohongshu",
                post_ids=post_ids,
                is_admin=False,
            )
        )
        ready = self.artifacts.ready_post_ids(
            platform="xiaohongshu",
            post_ids=post_ids,
            dataset_schema_version=DATASET_SCHEMA_VERSION,
        )
        return {
            "creator_id": creator_id,
            "total": self.posts.count_for_creator(
                platform="xiaohongshu",
                creator_id=creator_id,
            ),
            "offset": offset,
            "items": [
                {
                    "post_id": str(item["post_id"]),
                    "title": item.get("title") or "",
                    "published_at": item.get("published_at"),
                    "likes": item.get("like_count"),
                    "comments": item.get("reported_comment_count"),
                    "available": (
                        True
                        if settings.agent_free_mode
                        else str(item["post_id"]) in unlocked
                    ),
                    "dataset_ready": str(item["post_id"]) in ready,
                }
                for item in items
            ],
        }

    def dataset_prepare(self, post_id: str) -> dict[str, Any]:
        post = self.posts.get_access_context(
            platform="xiaohongshu",
            post_id=post_id,
        )
        if post is None:
            raise ValueError(f"Unknown post: {post_id}")

        settings = get_settings()
        if settings.agent_free_mode:
            if self.principal.user_id != 0:
                self.access.grant_dataset_entitlement(
                    user_id=self.principal.user_id,
                    platform="xiaohongshu",
                    post_id=post_id,
                    source="free_mode",
                )
            job_id = self.queue.enqueue_dataset_generation(
                post_id=post_id,
                platform="xiaohongshu",
            )
            artifact = self.artifacts.get(
                platform="xiaohongshu",
                post_id=post_id,
                dataset_schema_version=DATASET_SCHEMA_VERSION,
            )
            return {
                "post_id": post_id,
                "status": "READY" if artifact is not None else "PREPARING",
                "free": True,
                "generation_job_id": job_id,
            }

        # Dormant commercial path kept for future productization.
        already = self.access.has_entitlement(
            user_id=self.principal.user_id,
            platform="xiaohongshu",
            post_id=post_id,
            is_admin=False,
        )
        if not already:
            return {
                "post_id": post_id,
                "status": "COMMERCIAL_CONFIRMATION_REQUIRED",
            }

        job_id = self.queue.enqueue_dataset_generation(
            post_id=post_id,
            platform="xiaohongshu",
        )
        return {
            "post_id": post_id,
            "status": "PREPARING",
            "free": False,
            "generation_job_id": job_id,
        }

    def dataset_unlock(
        self,
        post_id: str,
        *,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Backward-compatible commercial helper; Agent tools use prepare."""
        settings = get_settings()
        if settings.agent_free_mode:
            return self.dataset_prepare(post_id)

        post = self.posts.get_access_context(
            platform="xiaohongshu",
            post_id=post_id,
        )
        if post is None:
            raise ValueError(f"Unknown post: {post_id}")

        already = self.access.has_entitlement(
            user_id=self.principal.user_id,
            platform="xiaohongshu",
            post_id=post_id,
            is_admin=False,
        )
        if not already and not confirm:
            account = self.account_status()
            return {
                "post_id": post_id,
                "status": "CONFIRMATION_REQUIRED",
                "credit_cost": 0 if account["unlimited"] else 1,
                "free_credits": account.get("free_credits", 0),
                "paid_credits": account.get("paid_credits", 0),
            }

        result = self.saas.unlock(
            principal=self.principal,
            platform="xiaohongshu",
            post_id=post_id,
        )
        if not result["allowed"]:
            return {
                "post_id": post_id,
                "status": "PAYMENT_REQUIRED",
                "credits": result["credits"],
            }

        job_id = self.queue.enqueue_dataset_generation(
            post_id=post_id,
            platform="xiaohongshu",
        )
        return {
            "post_id": post_id,
            "status": "UNLOCKED",
            "charged": bool(result["charged"]),
            "source": result["source"],
            "generation_job_id": job_id,
            "credits": result["credits"],
        }

    def dataset_status(self, post_id: str) -> dict[str, Any]:
        self._require_dataset_access(post_id)
        artifact = self.artifacts.get(
            platform="xiaohongshu",
            post_id=post_id,
            dataset_schema_version=DATASET_SCHEMA_VERSION,
        )
        key = (
            f"dataset-generation:xiaohongshu:{post_id}:"
            f"schema:{DATASET_SCHEMA_VERSION}"
        )
        job = self.jobs.get_by_idempotency_key(
            idempotency_key=key,
        )
        return {
            "post_id": post_id,
            "ready": artifact is not None,
            "status": (
                "READY"
                if artifact is not None
                else (job["status"] if job else "NOT_STARTED")
            ),
            "job_id": job["id"] if job else None,
            "error": job.get("last_error") if job else None,
        }

    def dataset_get(self, post_id: str) -> dict[str, Any]:
        self._require_dataset_access(post_id)
        status = self.dataset_status(post_id)
        if not status["ready"]:
            return status
        view = SimpleDatasetViewService().build(
            user_id=self.principal.user_id,
            post_id=post_id,
        )
        return {
            "post_id": post_id,
            "ready": True,
            "title": view.get("title") or "",
            "summary": view.get("summary") or "",
            "key_points": view.get("key_points") or [],
            "topics": view.get("topics") or [],
            "comment_insights": view.get("comment_insights") or [],
            "metrics": view.get("metrics") or {},
            "source_url": view.get("source_url"),
        }

    def dataset_content(
        self,
        post_id: str,
        *,
        max_text_units: int = 80,
        max_comments: int = 80,
    ) -> dict[str, Any]:
        self._require_dataset_access(post_id)
        status = self.dataset_status(post_id)
        if not status["ready"]:
            return status

        bundle = self.exports.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")
        units = self.text_units.list_for_post(post_id=post_id)
        comments = bundle["comments"]

        return {
            "post_id": post_id,
            "ready": True,
            "title": bundle["post"].get("title") or "",
            "author_text": bundle["post"].get("content") or "",
            "text_units": [
                {
                    "type": item.get("unit_type"),
                    "text": item.get("text") or "",
                    "provenance": item.get("provenance"),
                    "confidence": item.get("confidence"),
                }
                for item in units[: max(1, min(max_text_units, 200))]
            ],
            "comments": [
                {
                    "comment_id": item.get("comment_id"),
                    "parent_comment_id": item.get("parent_comment_id"),
                    "depth": item.get("depth"),
                    "author_name": item.get("author_name"),
                    "content": item.get("content") or "",
                    "like_count": item.get("like_count"),
                }
                for item in comments[: max(1, min(max_comments, 200))]
            ],
            "text_units_total": len(units),
            "comments_total": len(comments),
        }

    def dataset_comments(
        self,
        post_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        self._require_dataset_access(post_id)
        bundle = self.exports.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")
        comments = bundle["comments"]
        offset = max(0, offset)
        limit = max(1, min(limit, 100))
        page = comments[offset : offset + limit]
        return {
            "post_id": post_id,
            "total": len(comments),
            "offset": offset,
            "next_offset": (
                offset + len(page)
                if offset + len(page) < len(comments)
                else None
            ),
            "items": [
                {
                    "comment_id": item.get("comment_id"),
                    "parent_comment_id": item.get("parent_comment_id"),
                    "depth": item.get("depth"),
                    "author_name": item.get("author_name"),
                    "content": item.get("content") or "",
                    "like_count": item.get("like_count"),
                }
                for item in page
            ],
        }

    def _require_creator_access(self, creator_id: str) -> None:
        allowed = self.access.has_creator_submission(
            user_id=self.principal.user_id,
            platform="xiaohongshu",
            creator_id=creator_id,
            is_admin=self.principal.is_admin,
        )
        if not allowed:
            raise AgentAccessError(
                "Submit this Creator before accessing its catalog."
            )

    def _require_dataset_access(self, post_id: str) -> None:
        if get_settings().agent_free_mode:
            return
        allowed = self.access.has_entitlement(
            user_id=self.principal.user_id,
            platform="xiaohongshu",
            post_id=post_id,
            is_admin=self.principal.is_admin,
        )
        if not allowed:
            raise AgentAccessError(
                "This Dataset is not unlocked for the current user."
            )
