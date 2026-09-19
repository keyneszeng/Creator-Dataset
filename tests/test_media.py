import hashlib
from pathlib import Path

import pytest

from app.services.media import UnsafeMediaUrl, _suffix_for, _validate_remote_url


def test_suffix_uses_url_when_available() -> None:
    assert _suffix_for("image/jpeg", "https://example.com/a.webp") == ".webp"


def test_suffix_falls_back_to_content_type() -> None:
    assert _suffix_for("image/jpeg", "https://example.com/resource") == ".jpg"


def test_rejects_localhost() -> None:
    with pytest.raises(UnsafeMediaUrl):
        _validate_remote_url("http://localhost/image.jpg")


def test_sha256_fixture(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg"
    path.write_bytes(b"image-data")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(digest) == 64
