from pathlib import Path

from app.agent.service import AgentService
from app.core import database
from app.core.repositories import PostRepository
from app.core.settings import Settings
from app.saas.models import Principal, UserRole
from app.saas.sqlite_repository import SqliteSaasRepository


def test_agent_member_prepares_datasets_for_free(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_path=tmp_path / "agent-member.sqlite3",
        data_dir=tmp_path / "data",
        storage_backend="local",
        storage_local_dir=tmp_path / "objects",
        saas_default_free_dataset_credits=5,
        agent_free_mode=True,
    )
    settings.ensure_directories()
    database.init_database(settings.database_path)

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.repositories.factory.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.agent.service.get_settings",
        lambda: settings,
    )

    access = SqliteSaasRepository()
    user = access.create_user(
        email="agent@example.com",
        display_name="Agent User",
        role="member",
        free_credits=5,
    )
    user_id = int(user["id"])

    access.record_creator_submission(
        user_id=user_id,
        platform="xiaohongshu",
        creator_id="creator-1",
        submitted_url=(
            "https://www.xiaohongshu.com/user/profile/creator-1"
        ),
    )

    posts = PostRepository()
    posts.upsert_discovered(
        platform="xiaohongshu",
        creator_id="creator-1",
        post_id="post-1",
        source_url="https://example.test/post-1",
        title="Post 1",
        post_type="normal",
        raw={},
        platform_context={},
    )

    service = AgentService(
        principal=Principal(
            user_id=user_id,
            email="agent@example.com",
            role=UserRole.MEMBER,
        )
    )

    account = service.account_status()
    assert account["mode"] == "free"
    assert account["unlimited"] is True

    catalog = service.creator_posts("creator-1")
    assert catalog["items"][0]["available"] is True

    before = access.credit_balance(user_id=user_id)
    prepared = service.dataset_prepare("post-1")
    assert prepared["status"] == "PREPARING"
    assert prepared["free"] is True

    after = access.credit_balance(user_id=user_id)
    assert after == before

    assert access.has_entitlement(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-1",
        is_admin=False,
    ) is True

    repeated = service.dataset_prepare("post-1")
    assert repeated["free"] is True
    assert access.credit_balance(user_id=user_id) == before
