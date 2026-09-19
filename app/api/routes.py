from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.core.repositories import JobRepository, WorkerRepository
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
from app.services.creator_pipeline import CreatorPipelineService
from app.services.export import ExportService
from app.services.media_pipeline import MediaPipelineService
from app.services.ocr import OcrService
from app.services.post_detail import PostDetailService
from app.services.queue import QueueService
from app.services.stt import SttService

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


class ProcessMediaRequest(BaseModel):
    download_limit: int = Field(default=200, ge=1, le=2000)
    run_ocr: bool = True
    ocr_limit: int = Field(default=500, ge=1, le=5000)
    run_stt: bool = True
    stt_limit: int = Field(default=20, ge=1, le=200)


class TranscribeVideosRequest(BaseModel):
    only_missing: bool = True
    limit: int = Field(default=20, ge=1, le=200)


class CreatorPipelineRequest(BaseModel):
    max_posts: int = Field(default=20, ge=1, le=500)
    run_comments: bool = True
    run_media: bool = True
    run_ocr: bool = True
    run_stt: bool = True
    export: bool = True
    idempotency_key: str | None = Field(default=None, max_length=200)


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
        "media_registered": result.media_registered,
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


@router.post("/posts/{post_id}/process-media")
async def process_media(
    post_id: str,
    payload: ProcessMediaRequest,
) -> dict[str, object]:
    try:
        service = MediaPipelineService()
        return await service.process_post(
            post_id,
            download_limit=payload.download_limit,
            run_ocr=payload.run_ocr,
            ocr_limit=payload.ocr_limit,
            run_stt=payload.run_stt,
            stt_limit=payload.stt_limit,
        )
    except IntegrationNotInstalled as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "INTEGRATION_NOT_INSTALLED", "message": str(exc)},
        ) from exc


@router.post("/posts/{post_id}/export")
async def export_post(post_id: str) -> dict[str, str]:
    service = ExportService()
    try:
        return service.export_post(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/posts/{post_id}/transcribe-videos")
async def transcribe_videos(
    post_id: str,
    payload: TranscribeVideosRequest,
) -> dict[str, int]:
    try:
        service = SttService()
        return await service.process_post_videos(
            post_id,
            only_missing=payload.only_missing,
            limit=payload.limit,
        )
    except IntegrationNotInstalled as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "STT_INTEGRATION_NOT_INSTALLED", "message": str(exc)},
        ) from exc


@router.post("/creators/{creator_id}/run-pipeline")
async def run_creator_pipeline(
    creator_id: str,
    payload: CreatorPipelineRequest,
) -> dict[str, object]:
    service = CreatorPipelineService()
    try:
        result = await service.run(
            creator_id,
            max_posts=payload.max_posts,
            run_comments=payload.run_comments,
            run_media=payload.run_media,
            run_ocr=payload.run_ocr,
            run_stt=payload.run_stt,
            export=payload.export,
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
        "posts_selected": result.posts_selected,
        "posts_completed": result.posts_completed,
        "posts_failed": result.posts_failed,
        "job_id": result.job_id,
        "status": "COMPLETE" if result.posts_failed == 0 else "PARTIAL",
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: int) -> dict[str, object]:
    job = JobRepository().get(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return job


@router.post("/creators/{creator_id}/enqueue-pipeline")
async def enqueue_creator_pipeline(
    creator_id: str,
    payload: CreatorPipelineRequest,
) -> dict[str, object]:
    try:
        result = QueueService().enqueue_creator_pipeline(
            creator_id,
            max_posts=payload.max_posts,
            run_comments=payload.run_comments,
            run_media=payload.run_media,
            run_ocr=payload.run_ocr,
            run_stt=payload.run_stt,
            export=payload.export,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "creator_id": result.creator_id,
        "job_id": result.parent_job_id,
        "posts_enqueued": result.posts_enqueued,
        "status": "WAITING",
    }


@router.get("/jobs/{job_id}/progress")
async def get_job_progress(job_id: int) -> dict[str, object]:
    repository = JobRepository()
    job = repository.get(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return {
        "job": job,
        "children": repository.children_summary(parent_job_id=job_id),
    }


@router.get("/system/status")
async def system_status() -> dict[str, object]:
    jobs = JobRepository()
    workers = WorkerRepository()
    active_workers = workers.active()
    return {
        "queue": jobs.queue_summary(),
        "workers": {
            "active": len(active_workers),
            "items": active_workers,
        },
    }


@router.get("/jobs/{job_id}/tree")
async def get_job_tree(job_id: int) -> dict[str, object]:
    repository = JobRepository()
    root = repository.get(job_id=job_id)
    if root is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return {
        "root_job_id": job_id,
        "jobs": repository.job_tree(root_job_id=job_id),
    }


@router.post("/jobs/{job_id}/repair")
async def repair_job(job_id: int) -> dict[str, object]:
    repository = JobRepository()
    job = repository.get(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")

    repaired = repository.repair_subgraph(job_id=job_id)
    return {
        "job_id": job_id,
        "repaired_job_ids": repaired,
        "repaired_count": len(repaired),
    }
