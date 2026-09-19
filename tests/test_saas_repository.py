from pathlib import Path

from app.core import database
from app.saas.sqlite_repository import SqliteSaasRepository


def test_free_then_paid_dataset_credits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "saas.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    repository = SqliteSaasRepository()
    user = repository.create_user(
        email="member@example.com",
        display_name="Member",
        role="member",
        free_credits=5,
    )
    user_id = int(user["id"])

    for index in range(5):
        result = repository.unlock_dataset(
            user_id=user_id,
            platform="xiaohongshu",
            post_id=f"post-{index}",
            is_admin=False,
        )
        assert result["allowed"] is True
        assert result["source"] == "free_credit"

    balance = repository.credit_balance(user_id=user_id)
    assert balance["free"] == 0
    assert balance["paid"] == 0

    denied = repository.unlock_dataset(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-5",
        is_admin=False,
    )
    assert denied["allowed"] is False
    assert denied["source"] == "payment_required"

    # Unlocking an already-owned Dataset never charges twice.
    existing = repository.unlock_dataset(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-0",
        is_admin=False,
    )
    assert existing["allowed"] is True
    assert existing["charged"] is False
    assert repository.credit_balance(user_id=user_id)["total"] == 0

    repository.grant_credits(
        user_id=user_id,
        bucket="paid",
        amount=2,
        reason="test_purchase",
    )
    paid = repository.unlock_dataset(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-5",
        is_admin=False,
    )
    assert paid["allowed"] is True
    assert paid["source"] == "paid_credit"
    assert repository.credit_balance(user_id=user_id)["paid"] == 1


def test_admin_has_unlimited_dataset_access(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "admin.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    repository = SqliteSaasRepository()
    admin = repository.create_user(
        email="admin@example.com",
        display_name="Admin",
        role="admin",
        free_credits=0,
    )

    result = repository.unlock_dataset(
        user_id=int(admin["id"]),
        platform="xiaohongshu",
        post_id="anything",
        is_admin=True,
    )

    assert result["allowed"] is True
    assert result["charged"] is False
    assert result["source"] == "admin"
