import ipaddress
import socket
from urllib.parse import urlparse

from app.core.settings import Settings, get_settings


class UnsafeLlmEndpoint(ValueError):
    pass


def _allowed_hosts(settings: Settings) -> set[str]:
    return {
        item.strip().lower()
        for item in settings.llm_allowed_hosts.split(",")
        if item.strip()
    }


def validate_llm_base_url(
    base_url: str,
    *,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()

    if parsed.scheme not in {"http", "https"} or not host:
        raise UnsafeLlmEndpoint(
            "LLM base URL must be an absolute http/https URL."
        )

    if settings.deployment_mode == "local" and (
        settings.llm_allow_custom_base_url_local
    ):
        return base_url.rstrip("/")

    allowed = _allowed_hosts(settings)
    if host not in allowed:
        raise UnsafeLlmEndpoint(
            "LLM endpoint host is not allowed by this deployment."
        )

    if parsed.scheme != "https":
        raise UnsafeLlmEndpoint(
            "Cloud/SaaS LLM endpoints must use HTTPS."
        )

    try:
        addresses = socket.getaddrinfo(
            host,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeLlmEndpoint(
            "Could not resolve LLM endpoint hostname."
        ) from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeLlmEndpoint(
                "LLM endpoint resolves to a private/local address."
            )

    return base_url.rstrip("/")
