from mcp.server.transport_security import TransportSecuritySettings

from app.core.settings import Settings
from app.mcp_server import mcp


def _csv(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def build_mcp_asgi_app(settings: Settings):
    if settings.deployment_mode == "cloud":
        allowed_hosts = _csv(settings.mcp_allowed_hosts)
        if not allowed_hosts:
            raise ValueError(
                "Cloud MCP requires CREATOR_DATASET_MCP_ALLOWED_HOSTS."
            )
        allowed_origins = _csv(settings.mcp_allowed_origins)
    else:
        allowed_hosts = [
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ]
        allowed_origins = [
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ]

    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host=settings.mcp_host,
        transport_security=security,
    )
