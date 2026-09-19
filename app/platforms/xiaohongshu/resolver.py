from dataclasses import asdict, dataclass
from urllib.parse import urlparse


class InvalidCreatorUrl(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedCreator:
    platform: str
    creator_id: str
    canonical_url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


_ALLOWED_HOSTS = {
    "xiaohongshu.com",
    "www.xiaohongshu.com",
}


def resolve_creator_url(url: str) -> ResolvedCreator:
    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"}:
        raise InvalidCreatorUrl("URL must use http or https.")

    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise InvalidCreatorUrl("Unsupported host for Xiaohongshu creator URL.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3 or parts[0] != "user" or parts[1] != "profile":
        raise InvalidCreatorUrl(
            "Expected a Xiaohongshu creator URL like /user/profile/<creator_id>."
        )

    creator_id = parts[2].strip()
    if not creator_id:
        raise InvalidCreatorUrl("Creator ID is missing.")

    canonical_url = f"https://www.xiaohongshu.com/user/profile/{creator_id}"
    return ResolvedCreator(
        platform="xiaohongshu",
        creator_id=creator_id,
        canonical_url=canonical_url,
    )
