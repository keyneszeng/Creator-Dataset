import base64
from pathlib import Path

from app.core import database
from app.core.readiness import check_readiness
from app.core.settings import Settings


def _key() -> str:
    return base64.urlsafe_b64encode(b"r" * 32).decode("ascii")


def test_enabled_llm_requires_encryption_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "llm-readiness.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        llm_enabled=True,
        llm_credential_encryption_key="",
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.readiness.get_settings", lambda: settings)

    result = check_readiness()

    assert result["ready"] is False
    assert result["checks"]["llm_security"]["ok"] is False


def test_local_llm_with_key_is_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "llm-ready.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        llm_enabled=True,
        llm_credential_encryption_key=_key(),
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.readiness.get_settings", lambda: settings)

    result = check_readiness()

    assert result["ready"] is True
    assert result["checks"]["llm_security"]["ok"] is True
