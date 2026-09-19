import base64
from pathlib import Path

import pytest

from app.core import database
from app.core.settings import Settings
from app.llm.crypto import decrypt_secret, encrypt_secret
from app.llm.security import UnsafeLlmEndpoint, validate_llm_base_url


def _key() -> str:
    return base64.urlsafe_b64encode(b"k" * 32).decode("ascii")


def test_llm_secret_encrypts_roundtrip() -> None:
    encrypted = encrypt_secret("secret-api-key", key_text=_key())

    assert "secret-api-key" not in encrypted
    assert decrypt_secret(encrypted, key_text=_key()) == "secret-api-key"


def test_cloud_rejects_non_allowlisted_llm_host(tmp_path: Path) -> None:
    settings = Settings(
        deployment_mode="cloud",
        database_backend="sqlite",
        database_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        llm_enabled=True,
        llm_credential_encryption_key=_key(),
        llm_allowed_hosts="approved.example",
    )

    with pytest.raises(UnsafeLlmEndpoint):
        validate_llm_base_url(
            "https://unapproved.example/v1",
            settings=settings,
        )


def test_local_can_use_custom_self_hosted_llm(tmp_path: Path) -> None:
    settings = Settings(
        deployment_mode="local",
        database_backend="sqlite",
        database_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        llm_enabled=True,
        llm_credential_encryption_key=_key(),
        llm_allow_custom_base_url_local=True,
    )

    assert validate_llm_base_url(
        "http://127.0.0.1:11434/v1",
        settings=settings,
    ) == "http://127.0.0.1:11434/v1"
