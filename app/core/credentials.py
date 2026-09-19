from dataclasses import dataclass

from app.core.errors import AuthenticationRequired
from app.core.settings import get_settings


@dataclass(frozen=True, slots=True)
class XiaohongshuCredentials:
    cookie_header: str


def parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in value.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = raw_value.strip()
    return cookies


class EnvironmentCredentialProvider:
    """Reads credentials from environment-backed settings.

    Credentials are never persisted to SQLite and must not be logged.
    """

    def get_xiaohongshu(self) -> XiaohongshuCredentials:
        cookie_header = get_settings().xhs_cookie.strip()
        if not cookie_header:
            raise AuthenticationRequired(
                "Set CREATOR_DATASET_XHS_COOKIE before importing Xiaohongshu data."
            )
        return XiaohongshuCredentials(cookie_header=cookie_header)
