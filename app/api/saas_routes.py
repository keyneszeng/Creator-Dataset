from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
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
from app.storage.factory import create_object_store_for_backend


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


class UpdateUserAccessRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    status: str | None = Field(default=None, pattern="^(active|suspended)$")


class CreateApiKeyRequest(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=100)


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


@router.get("/admin/users")
async def list_users(
    limit: int = 100,
    offset: int = 0,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    items = create_saas_repository().list_users(
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return {"count": len(items), "items": items}


@router.patch("/admin/users/{user_id}")
async def update_user_access(
    user_id: int,
    payload: UpdateUserAccessRequest,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    repository = create_saas_repository()
    updated = repository.update_user_access(
        user_id=user_id,
        role=payload.role,
        status=payload.status,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Unknown user or no change.")
    return {
        "user": repository.get_user(user_id=user_id),
        "credits": repository.credit_balance(user_id=user_id),
    }


@router.get("/admin/users/{user_id}/credits")
async def credit_ledger(
    user_id: int,
    limit: int = 200,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    repository = create_saas_repository()
    if repository.get_user(user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Unknown user.")
    items = repository.list_credit_ledger(
        user_id=user_id,
        limit=max(1, min(limit, 1000)),
    )
    return {
        "user_id": user_id,
        "balance": repository.credit_balance(user_id=user_id),
        "count": len(items),
        "items": items,
    }


@router.get("/admin/users/{user_id}/api-keys")
async def list_api_keys(
    user_id: int,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    repository = create_saas_repository()
    if repository.get_user(user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Unknown user.")
    items = repository.list_api_keys(user_id=user_id)
    return {"user_id": user_id, "count": len(items), "items": items}


@router.post("/admin/users/{user_id}/api-keys")
async def create_api_key(
    user_id: int,
    payload: CreateApiKeyRequest,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return SaasService().create_api_key(
            user_id=user_id,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/admin/users/{user_id}/api-keys/{api_key_id}/revoke")
async def revoke_api_key(
    user_id: int,
    api_key_id: int,
    _: Principal = Depends(require_admin),
) -> dict[str, Any]:
    revoked = create_saas_repository().revoke_api_key(
        user_id=user_id,
        api_key_id=api_key_id,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Unknown or revoked API key.")
    return {"user_id": user_id, "api_key_id": api_key_id, "revoked": True}


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

    store = create_object_store_for_backend(
        str(artifact["storage_backend"])
    )
    downloads: dict[str, str] = {}
    for name, key in artifact["artifacts"].items():
        signed = store.access_url(key=str(key), expires_seconds=900)
        downloads[name] = signed or (
            f"/api/saas/datasets/{post_id}/files/{name}"
        )

    return {
        "post_id": post_id,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "ready": True,
        "generated_at": artifact.get("generated_at"),
        "storage_backend": artifact.get("storage_backend"),
        "downloads": downloads,
        "generation_job": job,
    }


@router.get("/datasets/{post_id}/files/{artifact_name}")
async def download_dataset_file(
    post_id: str,
    artifact_name: str,
    principal: Principal = Depends(require_principal),
):
    platform = "xiaohongshu"
    access = create_saas_repository()
    if not access.has_entitlement(
        user_id=principal.user_id,
        platform=platform,
        post_id=post_id,
        is_admin=principal.is_admin,
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "DATASET_NOT_UNLOCKED"},
        )

    artifact = create_dataset_artifact_repository().get(
        platform=platform,
        post_id=post_id,
        dataset_schema_version=DATASET_SCHEMA_VERSION,
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Dataset is not ready.")

    key = artifact["artifacts"].get(artifact_name)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown Dataset artifact.")

    store = create_object_store_for_backend(
        str(artifact["storage_backend"])
    )
    signed = store.access_url(key=str(key), expires_seconds=900)
    if signed:
        return RedirectResponse(url=signed, status_code=307)

    def iter_file():
        with store.materialize(key=str(key)) as path:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{artifact_name}"'
            )
        },
    )
