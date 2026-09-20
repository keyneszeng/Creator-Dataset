import sys

from mcp.server import MCPServer

from app.agent.identity import resolve_mcp_principal
from app.agent.service import AgentService
from app.core.database import init_database
from app.core.settings import get_settings
from app.postgres.database import init_postgres_database


mcp = MCPServer(
    "creator-dataset",
    instructions=(
        "Use Creator Dataset to import public creator profiles, browse compact "
        "post catalogs, prepare structured datasets on demand, and "
        "retrieve structured creator knowledge for analysis. Prefer compact "
        "tools first and fetch detailed content only when needed."
    ),
)


def _service() -> AgentService:
    return AgentService(principal=resolve_mcp_principal())


@mcp.tool()
def account_status() -> dict:
    """Return the current Agent access mode and role."""
    return _service().account_status()


@mcp.tool()
def creator_submit(url: str, max_pages: int = 20) -> dict:
    """
    Submit a public Creator profile URL for background import.

    The import is asynchronous and free.
    """
    return _service().creator_submit(url, max_pages=max_pages)


@mcp.tool()
def creator_status(creator_id: str) -> dict:
    """Check Creator import status and the number of discovered Posts."""
    return _service().creator_status(creator_id)


@mcp.tool()
def creator_posts(
    creator_id: str,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Browse a compact Creator Post catalog for free.

    Results include title, date, engagement, availability, and readiness.
    """
    return _service().creator_posts(
        creator_id,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def dataset_prepare(post_id: str) -> dict:
    """
    Prepare the full structured Dataset for a Post.

    This capability is available directly in the current personal-use mode.
    """
    return _service().dataset_prepare(post_id)


@mcp.tool()
def dataset_status(post_id: str) -> dict:
    """Check whether an prepared Dataset has finished generating."""
    return _service().dataset_status(post_id)


@mcp.tool()
def dataset_get(post_id: str) -> dict:
    """
    Get the compact user-facing Dataset view.

    Prefer this before requesting full normalized text or comments.
    """
    return _service().dataset_get(post_id)


@mcp.tool()
def dataset_content(
    post_id: str,
    max_text_units: int = 80,
    max_comments: int = 80,
) -> dict:
    """
    Get bounded normalized Dataset content for deeper Agent analysis.

    Includes author text, OCR/STT/comment text units and a bounded comment set.
    Use only after dataset_get when more evidence is needed.
    """
    return _service().dataset_content(
        post_id,
        max_text_units=max_text_units,
        max_comments=max_comments,
    )


@mcp.tool()
def dataset_comments(
    post_id: str,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """Page through comments for an unlocked Dataset."""
    return _service().dataset_comments(
        post_id,
        offset=offset,
        limit=limit,
    )


def _init_runtime() -> None:
    settings = get_settings()
    if settings.database_backend == "sqlite":
        init_database(settings.database_path)
    else:
        init_postgres_database(str(settings.database_url))


def main() -> None:
    _init_runtime()
    settings = get_settings()
    if settings.deployment_mode == "cloud":
        raise SystemExit(
            "Cloud MCP must run through the unified ASGI service: "
            "uvicorn app.main:app --host 0.0.0.0 --port 8000"
        )
    transport = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "streamable-http"
    )
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )


if __name__ == "__main__":
    main()
