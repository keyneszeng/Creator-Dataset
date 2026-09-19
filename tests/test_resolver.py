import pytest

from app.platforms.xiaohongshu.resolver import (
    InvalidCreatorUrl,
    resolve_creator_url,
)


def test_resolve_creator_url_strips_query_params() -> None:
    result = resolve_creator_url(
        "https://www.xiaohongshu.com/user/profile/abc123?xsec_token=secret"
    )

    assert result.platform == "xiaohongshu"
    assert result.creator_id == "abc123"
    assert (
        result.canonical_url
        == "https://www.xiaohongshu.com/user/profile/abc123"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/user/profile/abc",
        "https://www.xiaohongshu.com/explore/abc",
        "not-a-url",
    ],
)
def test_rejects_invalid_creator_urls(url: str) -> None:
    with pytest.raises(InvalidCreatorUrl):
        resolve_creator_url(url)
