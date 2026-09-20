from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl

from app.agent.service import AgentAccessError, AgentService


router = APIRouter(prefix="/v1", tags=["agent"])


class CreatorSubmitRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=20, ge=1, le=200)


def _service() -> AgentService:
    return AgentService()


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AgentAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/account")
async def account_status() -> dict[str, Any]:
    return _service().account_status()


@router.post("/creators", status_code=202)
async def submit_creator(
    payload: CreatorSubmitRequest,
) -> dict[str, Any]:
    service = _service()
    return _call(
        service.creator_submit,
        str(payload.url),
        max_pages=payload.max_pages,
    )


@router.get("/creators/{creator_id}")
async def creator_status(creator_id: str) -> dict[str, Any]:
    service = _service()
    return _call(service.creator_status, creator_id)


@router.get("/creators/{creator_id}/posts")
async def creator_posts(
    creator_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    service = _service()
    return _call(
        service.creator_posts,
        creator_id,
        limit=limit,
        offset=offset,
    )


@router.post("/datasets/{post_id}/prepare", status_code=202)
async def prepare_dataset(post_id: str) -> dict[str, Any]:
    service = _service()
    return _call(service.dataset_prepare, post_id)


@router.get("/datasets/{post_id}")
async def get_dataset(post_id: str) -> dict[str, Any]:
    service = _service()
    return _call(service.dataset_get, post_id)


@router.get("/datasets/{post_id}/status")
async def dataset_status(post_id: str) -> dict[str, Any]:
    service = _service()
    return _call(service.dataset_status, post_id)


@router.get("/datasets/{post_id}/content")
async def dataset_content(
    post_id: str,
    max_text_units: int = Query(default=80, ge=1, le=200),
    max_comments: int = Query(default=80, ge=1, le=200),
) -> dict[str, Any]:
    service = _service()
    return _call(
        service.dataset_content,
        post_id,
        max_text_units=max_text_units,
        max_comments=max_comments,
    )


@router.get("/datasets/{post_id}/comments")
async def dataset_comments(
    post_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    service = _service()
    return _call(
        service.dataset_comments,
        post_id,
        offset=offset,
        limit=limit,
    )
