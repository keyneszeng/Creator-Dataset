from pathlib import Path

import pytest

from app.core import database
from app.core.checkpoints import CheckpointRepository
from app.core.repositories import CreatorRepository, PostRepository
from app.services.creator_import import CreatorImportService


class FakeGateway:
    def get_creator(self, creator_id: str):
        return {
            "basic_info": {"nickname": "Test Creator"},
            "interactions": [{"type": "fans", "count": "10"}],
        }

    def get_creator_posts_page(self, creator_id: str, cursor: str = ""):
        if not cursor:
            return {
                "notes": [{"note_id": "n1", "display_title": "One"}],
                "cursor": "page-2",
                "has_more": True,
            }
        return {
            "notes": [{"note_id": "n2", "display_title": "Two"}],
            "cursor": "",
            "has_more": False,
        }


@pytest.mark.asyncio
async def test_import_creator_discovers_all_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "creator.sqlite3"
    database.init_database(db_path)

    original = database.get_settings

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    # Repository modules import db_session from database, so changing
    # database.get_settings is enough to redirect their connections.
    service = CreatorImportService(
        gateway=FakeGateway(),
        creator_repository=CreatorRepository(),
        post_repository=PostRepository(),
        checkpoint_repository=CheckpointRepository(),
    )

    result = await service.import_creator(
        "https://www.xiaohongshu.com/user/profile/creator-1"
    )

    assert result.creator_id == "creator-1"
    assert result.discovered_posts == 2
    assert result.discovery_finished is True

    monkeypatch.setattr(database, "get_settings", original)
