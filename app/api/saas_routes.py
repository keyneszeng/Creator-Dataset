from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.api.routes import _raise_platform_http_error
from app.core.errors import (
    AuthenticationRequired,
    IntegrationNotInstalled,
    PlatformBlocked,
    PlatformRequestError,
)
from app.core.versioning import DATASET_SCHEMA_VERSION
from app.platforms.xiaohongshu.resolver import InvalidCreatorUrl
from app.repositories.factory import (
    create_dataset_artifact_repository,
    create_job_repository,
    create_post_repository,
    create_saas_repository,
)
from app.saas.auth import require_admin, require_principal
from app.saas.models import Principal
from app.saas.service import SaasService
from app.services.creator_import import CreatorImportService
from app.services.queue import QueueService


router = APIRouter(prefix="/saas", tags=["saas"])


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)
    role: str = Field(default="member", pattern="^(admin|member)$")


class GrantCreditsRequest(BaseModel):
    bucket: str = Field(default="paid", pattern="^(free|paid)$")
    amount: int = Field(ge=1, le=1_000_000)
    reason: str = Field(default="admin_grant", min_length=1, max_length=200)
    reference_id: str | None = Field(default=None, max_length=200)


class SubmitCreatorRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=20, ge=1, le=200)


@router.post("/admin/users")
async def create_user(
    payload: CreateUserRequest,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return SaasService().create_user(
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper() or "duplicate" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "USER_EXISTS",
                    "message": "A user with this email already exists.",
                },
            ) from exc
        raise


@router.post("/admin/users/{user_id}/credits")
async def grant_credits(
    user_id: int,
    payload: GrantCreditsRequest,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    repository = create_saas_repository()
    user = repository.get_user(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Unknown user.")

    ledger_id = repository.grant_credits(
        user_id=user_id,
        bucket=payload.bucket,
        amount=payload.amount,
        reason=payload.reason,
        reference_id=payload.reference_id,
    )
    return {
        "ledger_id": ledger_id,
        "user_id": user_id,
        "credits": repository.credit_balance(user_id=user_id),
    }


@router.get("/me")
async def me(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return SaasService().account(principal)


@router.get("/me/entitlements")
async def my_entitlements(
    limit: int = 100,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if principal.is_admin and principal.user_id == 0:
        return {"count": 0, "items": [], "unlimited": True}

    items = create_saas_repository().list_entitlements(
        user_id=principal.user_id,
        limit=max(1, min(limit, 500)),
    )
    return {
        "count": len(items),
        "items": items,
        "unlimited": principal.is_admin,
    }


@router.post("/creators/submit")
async def submit_creator(
    payload: SubmitCreatorRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    service = CreatorImportService()
    try:
        result = await service.import_creator(
            str(payload.url),
            max_pages=payload.max_pages,
        )
    except InvalidCreatorUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (
        AuthenticationRequired,
        IntegrationNotInstalled,
        PlatformBlocked,
        PlatformRequestError,
    ) as exc:
        _raise_platform_http_error(exc)
        raise AssertionError("unreachable")

    if principal.user_id != 0:
        create_saas_repository().record_creator_submission(
            user_id=principal.user_id,
            platform="xiaohongshu",
            creator_id=result.creator_id,
            submitted_url=str(payload.url),
        )

    return {
        "creator_id": result.creator_id,
        "discovered_posts": result.discovered_posts,
        "discovery_finished": result.discovery_finished,
        "next_cursor": result.next_cursor,
    }


@router.post("/datasets/{post_id}/unlock")
async def unlock_dataset(
    post_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    platform = "xiaohongshu"
    post = create_post_repository().get_access_context(
        platform=platform,
        post_id=post_id,
    )
    if post is None:
        raise HTTPException(status_code=404, detail=f"Unknown post: {post_id}")

    result = SaasService().unlock(
        principal=principal,
        platform=platform,
        post_id=post_id,
    )
    if not result["allowed"]:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "PAYMENT_REQUIRED",
                "message": (
                    "Free Dataset credits are exhausted. "
                    "Purchase or receive additional credits to unlock more."
                ),
                "credits": result["credits"],
            },
        )

    job_id = QueueService().enqueue_dataset_generation(
        post_id=post_id,
        platform=platform,
    )
    result["generation_job_id"] = job_id
    return result


@router.get("/datasets/{post_id}")
async def get_dataset(
    post_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    platform = "xiaohongshu"
    repository = create_saas_repository()

    if not repository.has_entitlement(
        user_id=principal.user_id,
        platform=platform,
        post_id=post_id,
        is_admin=principal.is_admin,
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "DATASET_NOT_UNLOCKED",
                "message": "Unlock this Dataset before accessing it.",
            },
        )

    artifact = create_dataset_artifact_repository().get(
        platform=platform,
        post_id=post_id,
        dataset_schema_version=DATASET_SCHEMA_VERSION,
    )
    generation_key = (
        f"dataset-generation:{platform}:{post_id}:"
        f"schema:{DATASET_SCHEMA_VERSION}"
    )
    job = create_job_repository().get_by_idempotency_key(
        idempotency_key=generation_key,
    )

    if artifact is None:
        return {
            "post_id": post_id,
            "dataset_schema_version": DATASET_SCHEMA_VERSION,
            "ready": False,
            "generation_job": job,
        }

    return {
        "post_id": post_id,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "ready": True,
        "generated_at": artifact.get("generated_at"),
        "storage_backend": artifact.get("storage_backend"),
        "artifacts": artifact["artifacts"],
        "generation_job": job,
    }
