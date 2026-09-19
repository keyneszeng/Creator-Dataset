from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.saas_routes import router as saas_router
from app.core.database import init_database
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.postgres.database import init_postgres_database
from app.postgres.pool import close_postgres_pools
from app.saas.auth import authenticate_headers


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

@app.middleware("http")
async def protect_internal_api(request: Request, call_next):
    settings = get_settings()
    path = request.url.path

    public_paths = {
        "/api/health",
        "/api/system/readiness",
        "/api/system/capabilities",
    }

    if (
        getattr(settings, "saas_auth_enabled", False)
        and path.startswith("/api/")
        and not path.startswith("/api/saas/")
        and path not in public_paths
    ):
        try:
            principal = authenticate_headers(
                authorization=request.headers.get("authorization"),
                x_api_key=request.headers.get("x-api-key"),
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", 401)
            detail = getattr(
                exc,
                "detail",
                {
                    "code": "AUTH_REQUIRED",
                    "message": "Administrator API key is required.",
                },
            )
            return JSONResponse(
                status_code=status_code,
                content={"detail": detail},
            )

        if not principal.is_admin:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "code": "ADMIN_REQUIRED",
                        "message": (
                            "This is an internal/admin API. "
                            "Use /api/saas endpoints for member access."
                        ),
                    }
                },
            )

    return await call_next(request)


app.include_router(router, prefix="/api")
app.include_router(saas_router, prefix="/api")
