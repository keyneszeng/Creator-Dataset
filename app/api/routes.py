from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.core.errors import (
    AuthenticationRequired,
    IntegrationNotInstalled,
    PlatformBlocked,
    PlatformRequestError,
)
from app.platforms.xiaohongshu import XiaohongshuAdapter
from app.platforms.xiaohongshu.resolver import InvalidCreatorUrl
from app.services.comment_crawl import CommentCrawlService
from app.services.creator_import import CreatorImportService
from app.services.ocr import OcrService
from app.services.post_detail import PostDetailService

router = APIRouter()


class ResolveCreatorRequest(BaseModel):
    url: HttpUrl


class ImportCreatorRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=20, ge=1, le=200)


class EnrichPostsRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    only_missing: bool = True


class CrawlCommentsRequest(BaseModel):
    max_root_pages: int = Field(default=200, ge=1, le=1000)
    max_reply_pages: int = Field(default=200, ge=1, le=1000)


class OcrImagesRequest(BaseModel):
    include_comment_images: bool = True
    only_missing: bool = True
    limit: int = Field(default=200, ge=1, le=2000)


def _raise_platform_http_error(exc: Exception) -> None:
    if isinstance(exc, AuthenticationRequired):
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": str(exc)},
        ) from exc
    if isinstance(exc, IntegrationNotInstalled):
        raise HTTPException(
            status_code=503,
            detail={"code": "INTEGRATION_NOT_INSTALLED", "message": str(exc)},
        ) from exc
    if isinstance(exc, PlatformBlocked):
        raise HTTPException(
            status_code=429,
            detail={"code": "PLATFORM_BLOCKED", "message": str(exc)},
        ) from exc
    if isinstance(exc, PlatformRequestError):
        raise HTTPException(
            status_code=502,
            detail={"code": "PLATFORM_REQUEST_ERROR", "message": str(exc)},
        ) from exc
    raise exc


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/creators/resolve")
async def resolve_creator(payload: ResolveCreatorRequest) -> dict[str, str]:
    adapter = XiaohongshuAdapter()
    try:
        return await adapter.resolve_creator(str(payload.url))
    except InvalidCreatorUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/creators/import")
async def import_creator(payload: ImportCreatorRequest) -> dict[str, object]:
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

    return {
        "creator_id": result.creator_id,
        "discovered_posts": result.discovered_posts,
        "discovery_finished": result.discovery_finished,
        "next_cursor": result.next_cursor,
    }


@router.post("/creators/{creator_id}/enrich-posts")
async def enrich_posts(
    creator_id: str,
    payload: EnrichPostsRequest,
) -> dict[str, object]:
    service = PostDetailService()
    try:
        result = await service.enrich_creator(
            creator_id,
            limit=payload.limit,
            only_missing=payload.only_missing,
        )
    except (
        AuthenticationRequired,
        IntegrationNotInstalled,
        PlatformBlocked,
        PlatformRequestError,
    ) as exc:
        _raise_platform_http_error(exc)
        raise AssertionError("unreachable")

    return {
        "creator_id": result.creator_id,
        "requested": result.requested,
        "enriched": result.enriched,
    }


@router.post("/posts/{post_id}/crawl-comments")
async def crawl_comments(
    post_id: str,
    payload: CrawlCommentsRequest,
) -> dict[str, object]:
    service = CommentCrawlService()
    try:
        result = await service.crawl_post(
            post_id,
            max_root_pages=payload.max_root_pages,
            max_reply_pages=payload.max_reply_pages,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        AuthenticationRequired,
        IntegrationNotInstalled,
        PlatformBlocked,
        PlatformRequestError,
    ) as exc:
        _raise_platform_http_error(exc)
        raise AssertionError("unreachable")

    return {
        "post_id": result.post_id,
        "root_comments": result.root_comments,
        "reply_comments": result.reply_comments,
        "failed_threads": result.failed_threads,
        "status": result.status,
        "completeness_ratio": result.completeness_ratio,
    }


@router.post("/posts/{post_id}/ocr-images")
async def ocr_images(
    post_id: str,
    payload: OcrImagesRequest,
) -> dict[str, int]:
    try:
        service = OcrService()
        return await service.process_post_images(
            post_id,
            include_comment_images=payload.include_comment_images,
            only_missing=payload.only_missing,
            limit=payload.limit,
        )
    except IntegrationNotInstalled as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "OCR_INTEGRATION_NOT_INSTALLED", "message": str(exc)},
        ) from exc
