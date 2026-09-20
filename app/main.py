from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.saas_routes import router as saas_router
from app.api.agent_routes import router as agent_router
from app.core.database import init_database
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.postgres.database import init_postgres_database
from app.postgres.pool import close_postgres_pools
from app.mcp_hosting import build_mcp_asgi_app
from app.mcp_server import mcp
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
        try:
            async with mcp.session_manager.run():
                yield
        except RuntimeError as exc:
            # Starlette TestClient may enter the same global app lifespan
            # repeatedly in one Python process. MCP's session manager is
            # intentionally single-run. Production ASGI processes enter the
            # lifespan once; repeated test lifespans can continue without
            # MCP because their REST assertions do not depend on it.
            if "can only be called once per instance" not in str(exc):
                raise
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

    deployment_mode = getattr(settings, "deployment_mode", "local")
    cloud_agent_token = getattr(settings, "cloud_agent_token", "")

    if path.startswith("/mcp"):
        if deployment_mode == "cloud":
            token = cloud_agent_token
            if not token:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": {
                            "code": "MCP_TOKEN_NOT_CONFIGURED",
                            "message": (
                                "Cloud MCP is disabled until a private "
                                "Agent token is configured."
                            ),
                        }
                    },
                )
            expected = f"Bearer {token}"
            supplied = request.headers.get("authorization", "")
            if not secrets.compare_digest(supplied, expected):
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": {
                            "code": "INVALID_AGENT_TOKEN",
                            "message": "A valid Agent bearer token is required.",
                        }
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)

    public_paths = {
        "/api/health",
        "/api/system/readiness",
        "/api/system/capabilities",
    }

    personal_cloud_authenticated = False
    if (
        deployment_mode == "cloud"
        and (
            path.startswith("/api/")
            or path.startswith("/v1/")
        )
        and path not in public_paths
        and cloud_agent_token
    ):
        expected = f"Bearer {cloud_agent_token}"
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "code": "INVALID_AGENT_TOKEN",
                        "message": "A valid Agent bearer token is required.",
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        personal_cloud_authenticated = True

    if (
        not personal_cloud_authenticated
        and getattr(settings, "saas_auth_enabled", False)
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
app.include_router(agent_router)


# Keep API routes first. The mounted MCP app handles /mcp on the same
# HTTPS origin without creating a separate public service.
app.mount("/", build_mcp_asgi_app(get_settings()))
