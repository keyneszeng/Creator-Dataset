from pathlib import Path

from app.core import database
from app.saas.sqlite_repository import SqliteSaasRepository


def test_duplicate_payment_event_grants_paid_credits_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "billing.sqlite3"
    database.init_database(db_path)

    class _Settings:
        database_path = db_path

    monkeypatch.setattr(database, "get_settings", lambda: _Settings())

    repository = SqliteSaasRepository()
    user = repository.create_user(
        email="buyer@example.com",
        display_name="Buyer",
        role="member",
        free_credits=0,
    )
    user_id = int(user["id"])

    first = repository.apply_paid_credit_purchase(
        provider="test",
        event_id="evt_001",
        user_id=user_id,
        credits=25,
        amount_minor=990,
        currency="usd",
        payload={"source": "unit-test"},
    )
    second = repository.apply_paid_credit_purchase(
        provider="test",
        event_id="evt_001",
        user_id=user_id,
        credits=25,
        amount_minor=990,
        currency="usd",
        payload={"source": "duplicate-delivery"},
    )

    assert first["applied"] is True
    assert second["applied"] is False
    assert first["billing_event_id"] == second["billing_event_id"]

    balance = repository.credit_balance(user_id=user_id)
    assert balance["paid"] == 25
    assert balance["total"] == 25

    ledger = repository.list_credit_ledger(
        user_id=user_id,
        limit=20,
    )
    payment_entries = [
        row for row in ledger
        if row["reason"] == "payment_purchase"
    ]
    assert len(payment_entries) == 1
