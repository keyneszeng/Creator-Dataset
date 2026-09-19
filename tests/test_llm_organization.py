import base64
from pathlib import Path

from app.core import database
from app.core.repositories import PostRepository
from app.core.settings import Settings
from app.llm.models import (
    LlmOrganizationTask,
    SimplifiedDatasetResult,
)
from app.repositories.factory import create_llm_repository
from app.saas.sqlite_repository import SqliteSaasRepository
from app.services.llm_organization import LlmOrganizationService
from app.services.simple_view import SimpleDatasetViewService


def _key() -> str:
    return base64.urlsafe_b64encode(b"z" * 32).decode("ascii")


class FakeAdapter:
    provider = "openai_compatible"

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url

    def organize(self, **kwargs):
        assert kwargs["api_key"] == "user-secret-key"
        assert "Author source text" in kwargs["source_text"]
        return SimplifiedDatasetResult(
            title="Simple Title",
            summary="Simple summary for the user.",
            key_points=["Point A", "Point B"],
            topics=["creator", "dataset"],
            comment_insights=["Audience asks for examples."],
        )


def test_user_llm_connection_is_encrypted_and_result_drives_simple_view(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        deployment_mode="local",
        database_backend="sqlite",
        database_path=tmp_path / "llm.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        llm_enabled=True,
        llm_credential_encryption_key=_key(),
        llm_allow_custom_base_url_local=True,
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.services.llm_organization.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.services.llm_organization.OpenAICompatibleAdapter",
        FakeAdapter,
    )

    access = SqliteSaasRepository()
    user = access.create_user(
        email="llm@example.com",
        display_name="LLM User",
        role="member",
        free_credits=5,
    )
    user_id = int(user["id"])

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="Original Title",
        post_type="normal",
        raw={},
        platform_context={},
    )
    with database.db_session(settings.database_path) as connection:
        connection.execute(
            "UPDATE posts SET content=? WHERE post_id=?",
            ("Author source text", "post-1"),
        )

    service = LlmOrganizationService()
    connection = service.create_connection(
        user_id=user_id,
        provider="openai_compatible",
        label="My Model",
        model="test-model",
        base_url="http://127.0.0.1:9999/v1",
        api_key="user-secret-key",
    )

    with database.db_session(settings.database_path) as db:
        stored = db.execute(
            "SELECT secret_ciphertext FROM llm_connections WHERE id=?",
            (connection["id"],),
        ).fetchone()
    assert stored is not None
    assert "user-secret-key" not in stored["secret_ciphertext"]

    run_id, job_id = service.create_run(
        user_id=user_id,
        post_id="post-1",
        connection_id=int(connection["id"]),
        task=LlmOrganizationTask.SIMPLIFY,
        custom_instruction=None,
    )
    assert job_id > 0

    service.execute_run(run_id=run_id)

    run = create_llm_repository(settings).get_run(
        user_id=user_id,
        run_id=run_id,
    )
    assert run is not None
    assert run["status"] == "COMPLETE"
    assert run["result"]["summary"] == "Simple summary for the user."

    view = SimpleDatasetViewService().build(
        user_id=user_id,
        post_id="post-1",
    )
    assert view["organized_by_ai"] is True
    assert view["summary"] == "Simple summary for the user."
    assert view["key_points"] == ["Point A", "Point B"]
