import os

import pytest

from app.postgres.database import init_postgres_database
from app.postgres.saas import PostgresSaasRepository


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def test_duplicate_postgres_payment_event_grants_once() -> None:
    init_postgres_database(str(DATABASE_URL))
    repository = PostgresSaasRepository(str(DATABASE_URL))

    with repository._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE
                    billing_events,
                    creator_submissions,
                    dataset_entitlements,
                    credit_ledger,
                    api_keys,
                    users
                RESTART IDENTITY CASCADE
                """
            )

    user = repository.create_user(
        email="billing@example.com",
        display_name="Billing",
        role="member",
        free_credits=0,
    )
    user_id = int(user["id"])

    first = repository.apply_paid_credit_purchase(
        provider="stripe",
        event_id="evt_same",
        user_id=user_id,
        credits=100,
        amount_minor=1999,
        currency="usd",
        payload={"type": "checkout.session.completed"},
    )
    second = repository.apply_paid_credit_purchase(
        provider="stripe",
        event_id="evt_same",
        user_id=user_id,
        credits=100,
        amount_minor=1999,
        currency="usd",
        payload={"type": "checkout.session.completed"},
    )

    assert first["applied"] is True
    assert second["applied"] is False
    assert repository.credit_balance(user_id=user_id)["paid"] == 100
