from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.core.database import init_database
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.postgres.database import init_postgres_database
from app.postgres.pool import close_postgres_pools


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()

    database_backend = getattr(settings, "database_backend", "sqlite")
    if database_backend == "sqlite":
        init_database(settings.database_path)
    else:
        init_postgres_database(str(settings.database_url))

    try:
        yield
    finally:
        if database_backend == "postgres":
            close_postgres_pools()


app = FastAPI(
    title="Creator Dataset",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api")
