from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.core.database import init_database
from app.core.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_database(settings.database_path)
    yield


app = FastAPI(
    title="Creator Dataset",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api")
