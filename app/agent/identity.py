import ipaddress

from app.core.settings import Settings, get_settings
from app.repositories.factory import create_saas_repository
from app.saas.models import Principal, UserRole
from app.saas.security import hash_api_key


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def resolve_mcp_principal(
    settings: Settings | None = None,
) -> Principal:
    settings = settings or get_settings()

    if not _is_loopback_host(settings.mcp_host):
        raise RuntimeError(
            "Remote MCP binding is disabled until OAuth 2.1 identity "
            "mapping is implemented. Bind the development server to "
            "127.0.0.1 and use a secure MCP tunnel for ChatGPT testing."
        )

    if settings.mcp_user_api_key:
        row = create_saas_repository().authenticate_api_key(
            key_hash=hash_api_key(settings.mcp_user_api_key),
        )
        if row is None:
            raise RuntimeError(
                "CREATOR_DATASET_MCP_USER_API_KEY is invalid or revoked."
            )
        return Principal(
            user_id=int(row["user_id"]),
            email=str(row["email"]),
            role=UserRole(str(row["role"])),
        )

    if settings.deployment_mode != "local":
        raise RuntimeError(
            "Cloud MCP requires user authentication. Configure a local "
            "Member API key for development or implement OAuth 2.1 before "
            "public deployment."
        )

    return Principal(
        user_id=0,
        email="local-agent@localhost",
        role=UserRole.ADMIN,
    )
