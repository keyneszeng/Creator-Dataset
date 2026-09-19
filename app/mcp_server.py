import sys

from mcp.server import MCPServer

from app.agent.service import AgentService
from app.core.database import init_database
from app.core.settings import get_settings
from app.postgres.database import init_postgres_database


mcp = MCPServer(
    "creator-dataset",
    instructions=(
        "Use Creator Dataset to import public creator profiles, browse compact "
        "post catalogs, unlock selected datasets only with user intent, and "
        "retrieve structured creator knowledge for analysis. Prefer compact "
        "tools first and fetch detailed content only when needed."
    ),
)


def _service() -> AgentService:
    return AgentService()


@mcp.tool()
def account_status() -> dict:
    """Return the current account role and Dataset credit balance."""
    return _service().account_status()


@mcp.tool()
def creator_submit(url: str, max_pages: int = 20) -> dict:
    """
    Submit a public Creator profile URL for background import.

    This does not consume Dataset credits. The import is asynchronous.
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
    Browse a compact Creator Post catalog without consuming Dataset credits.

    Results include title, date, engagement, unlock status, and readiness.
    """
    return _service().creator_posts(
        creator_id,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def dataset_unlock(post_id: str, confirm: bool = False) -> dict:
    """
    Preview or perform a Dataset unlock.

    Call with confirm=false first unless the user explicitly asked to unlock
    this specific Post. A new unlock may consume one free or paid credit.
    """
    return _service().dataset_unlock(post_id, confirm=confirm)


@mcp.tool()
def dataset_status(post_id: str) -> dict:
    """Check whether an unlocked Dataset has finished generating."""
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
