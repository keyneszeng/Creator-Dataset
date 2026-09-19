import time
from typing import Any

from app.core.rate_limit import SharedRateLimiter
from app.core.settings import get_settings

from app.core.credentials import EnvironmentCredentialProvider, parse_cookie_header
from app.core.errors import IntegrationNotInstalled, PlatformBlocked, PlatformRequestError


class XiaohongshuGateway:
    """Thin boundary around the optional Apache-2.0 xiaohongshu-cli package."""

    def __init__(self, credential_provider: EnvironmentCredentialProvider | None = None) -> None:
        self.credential_provider = credential_provider or EnvironmentCredentialProvider()
        self.rate_limiter = SharedRateLimiter(
            key="xiaohongshu-api",
            min_interval_seconds=get_settings().xhs_min_interval_seconds,
        )

    def _client(self):
        try:
            from xhs_cli.client import XhsClient
            from xhs_cli.exceptions import IpBlockedError, NeedVerifyError, SessionExpiredError, XhsApiError
        except ImportError as exc:
            raise IntegrationNotInstalled(
                'Install the Xiaohongshu integration with pip install -e ".[xhs]".'
            ) from exc

        credentials = self.credential_provider.get_xiaohongshu()
        cookies = parse_cookie_header(credentials.cookie_header)
        if not cookies:
            raise PlatformRequestError("Configured Xiaohongshu cookie is empty.")
        client = XhsClient(cookies=cookies)
        return client, (IpBlockedError, NeedVerifyError, SessionExpiredError), XhsApiError

    def _run(self, action):
        delay = self.rate_limiter.reserve_delay()
        if delay > 0:
            time.sleep(delay)

        client, blocked_errors, api_error = self._client()
        try:
            return action(client)
        except blocked_errors as exc:
            raise PlatformBlocked(str(exc)) from exc
        except api_error as exc:
            raise PlatformRequestError(str(exc)) from exc
        finally:
            client.close()

    def get_creator(self, creator_id: str) -> dict[str, Any]:
        return self._run(lambda client: client.get_user_info(creator_id))

    def get_creator_posts_page(self, creator_id: str, cursor: str = "") -> dict[str, Any]:
        return self._run(lambda client: client.get_user_notes(creator_id, cursor=cursor))

    def get_post_detail(self, post_id: str, *, xsec_token: str = "",
                        xsec_source: str = "pc_feed") -> dict[str, Any]:
        return self._run(lambda client: client.get_note_detail(
            post_id, xsec_token=xsec_token, xsec_source=xsec_source
        ))

    def get_comments_page(self, post_id: str, cursor: str = "", xsec_token: str = "",
                          xsec_source: str = "pc_feed") -> dict[str, Any]:
        return self._run(lambda client: client.get_comments(
            post_id, cursor=cursor, xsec_token=xsec_token, xsec_source=xsec_source
        ))

    def get_sub_comments_page(self, post_id: str, root_comment_id: str,
                              cursor: str = "") -> dict[str, Any]:
        return self._run(lambda client: client.get_sub_comments(
            post_id, root_comment_id, cursor=cursor
        ))
