from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.platforms.xiaohongshu import XiaohongshuAdapter
from app.platforms.xiaohongshu.resolver import InvalidCreatorUrl

router = APIRouter()


class ResolveCreatorRequest(BaseModel):
    url: HttpUrl


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
