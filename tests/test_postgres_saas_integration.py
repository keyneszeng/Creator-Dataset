import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.postgres.database import init_postgres_database
from app.postgres.saas import PostgresSaasRepository


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def _reset(repository: PostgresSaasRepository) -> None:
    with repository._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE
                    creator_submissions,
                    dataset_entitlements,
                    credit_ledger,
                    api_keys,
                    users
                RESTART IDENTITY CASCADE
                """
            )


def test_postgres_saas_free_credit_and_entitlement() -> None:
    init_postgres_database(str(DATABASE_URL))
    repository = PostgresSaasRepository(str(DATABASE_URL))
    _reset(repository)

    user = repository.create_user(
        email="member@example.com",
        display_name="Member",
        role="member",
        free_credits=5,
    )
    user_id = int(user["id"])

    first = repository.unlock_dataset(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-1",
        is_admin=False,
    )
    repeated = repository.unlock_dataset(
        user_id=user_id,
        platform="xiaohongshu",
        post_id="post-1",
        is_admin=False,
    )

    assert first["allowed"] is True
    assert first["charged"] is True
    assert repeated["allowed"] is True
    assert repeated["charged"] is False
    assert repository.credit_balance(user_id=user_id)["free"] == 4


def test_postgres_concurrent_unlock_cannot_overspend() -> None:
    init_postgres_database(str(DATABASE_URL))
    repository = PostgresSaasRepository(str(DATABASE_URL))
    _reset(repository)

    user = repository.create_user(
        email="race@example.com",
        display_name="Race",
        role="member",
        free_credits=1,
    )
    user_id = int(user["id"])

    def unlock(post_id: str):
        local = PostgresSaasRepository(str(DATABASE_URL))
        return local.unlock_dataset(
            user_id=user_id,
            platform="xiaohongshu",
            post_id=post_id,
            is_admin=False,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(unlock, ["post-a", "post-b"])
        )

    assert sum(1 for item in results if item["allowed"]) == 1
    assert sum(1 for item in results if not item["allowed"]) == 1

    balance = repository.credit_balance(user_id=user_id)
    assert balance["free"] == 0
    assert balance["total"] == 0

    entitlements = repository.list_entitlements(
        user_id=user_id,
        limit=10,
    )
    assert len(entitlements) == 1
