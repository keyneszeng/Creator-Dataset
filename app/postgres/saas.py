import json
from typing import Any

from app.postgres.pool import pooled_connection


class PostgresSaasRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return pooled_connection(self.database_url)

    def create_user(
        self,
        *,
        email: str,
        display_name: str | None,
        role: str,
        free_credits: int,
    ) -> dict[str, Any]:
        normalized = email.strip().lower()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (email, display_name, role)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (normalized, display_name, role),
                )
                user_id = int(cursor.fetchone()["id"])
                if free_credits > 0:
                    cursor.execute(
                        """
                        INSERT INTO credit_ledger (
                            user_id, bucket, delta, reason, reference_id
                        ) VALUES (%s, 'free', %s, 'signup_grant', NULL)
                        """,
                        (user_id, free_credits),
                    )
        return self.get_user(user_id=user_id) or {}

    def create_api_key(
        self,
        *,
        user_id: int,
        name: str,
        key_prefix: str,
        key_hash: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO api_keys (
                        user_id, name, key_prefix, key_hash
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, name, key_prefix, key_hash),
                )
                return int(cursor.fetchone()["id"])

    def authenticate_api_key(
        self,
        *,
        key_hash: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.id AS user_id, u.email, u.display_name,
                           u.role, u.status, k.id AS api_key_id,
                           k.key_prefix
                    FROM api_keys k
                    JOIN users u ON u.id=k.user_id
                    WHERE k.key_hash=%s
                      AND k.revoked_at IS NULL
                      AND u.status='active'
                    LIMIT 1
                    """,
                    (key_hash,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    "UPDATE api_keys SET last_used_at=NOW() WHERE id=%s",
                    (row["api_key_id"],),
                )
        return dict(row)

    def get_user(self, *, user_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE id=%s",
                    (user_id,),
                )
                row = cursor.fetchone()
        return dict(row) if row else None

    def credit_balance(self, *, user_id: int) -> dict[str, int]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT bucket, COALESCE(SUM(delta), 0) AS balance
                    FROM credit_ledger
                    WHERE user_id=%s
                    GROUP BY bucket
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        balances = {"free": 0, "paid": 0}
        for row in rows:
            balances[str(row["bucket"])] = int(row["balance"] or 0)
        balances["total"] = balances["free"] + balances["paid"]
        return balances

    def grant_credits(
        self,
        *,
        user_id: int,
        bucket: str,
        amount: int,
        reason: str,
        reference_id: str | None = None,
    ) -> int:
        if amount <= 0:
            raise ValueError("Credit grant amount must be positive.")
        if bucket not in {"free", "paid"}:
            raise ValueError("Credit bucket must be free or paid.")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO credit_ledger (
                        user_id, bucket, delta, reason, reference_id
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, bucket, amount, reason, reference_id),
                )
                return int(cursor.fetchone()["id"])

    def unlock_dataset(
        self,
        *,
        user_id: int,
        platform: str,
        post_id: str,
        is_admin: bool,
    ) -> dict[str, Any]:
        if is_admin:
            return {
                "allowed": True,
                "charged": False,
                "source": "admin",
                "post_id": post_id,
            }

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM users
                    WHERE id=%s AND status='active'
                    FOR UPDATE
                    """,
                    (user_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Unknown or inactive user.")

                cursor.execute(
                    """
                    SELECT source, granted_at
                    FROM dataset_entitlements
                    WHERE user_id=%s AND platform=%s AND post_id=%s
                    """,
                    (user_id, platform, post_id),
                )
                existing = cursor.fetchone()
                if existing:
                    return {
                        "allowed": True,
                        "charged": False,
                        "source": str(existing["source"]),
                        "post_id": post_id,
                    }

                cursor.execute(
                    """
                    SELECT bucket, COALESCE(SUM(delta), 0) AS balance
                    FROM credit_ledger
                    WHERE user_id=%s
                    GROUP BY bucket
                    """,
                    (user_id,),
                )
                balances = {"free": 0, "paid": 0}
                for row in cursor.fetchall():
                    balances[str(row["bucket"])] = int(row["balance"] or 0)

                if balances["free"] > 0:
                    bucket = "free"
                    source = "free_credit"
                elif balances["paid"] > 0:
                    bucket = "paid"
                    source = "paid_credit"
                else:
                    return {
                        "allowed": False,
                        "charged": False,
                        "source": "payment_required",
                        "post_id": post_id,
                    }

                cursor.execute(
                    """
                    INSERT INTO dataset_entitlements (
                        user_id, platform, post_id, source
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, platform, post_id, source),
                )
                cursor.execute(
                    """
                    INSERT INTO credit_ledger (
                        user_id, bucket, delta, reason, reference_id
                    ) VALUES (%s, %s, -1, 'dataset_unlock', %s)
                    """,
                    (user_id, bucket, f"{platform}:{post_id}"),
                )

        return {
            "allowed": True,
            "charged": True,
            "source": source,
            "post_id": post_id,
        }

    def has_entitlement(
        self,
        *,
        user_id: int,
        platform: str,
        post_id: str,
        is_admin: bool,
    ) -> bool:
        if is_admin:
            return True
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1
                    FROM dataset_entitlements
                    WHERE user_id=%s AND platform=%s AND post_id=%s
                      AND (expires_at IS NULL OR expires_at > NOW())
                    LIMIT 1
                    """,
                    (user_id, platform, post_id),
                )
                row = cursor.fetchone()
        return row is not None

    def record_creator_submission(
        self,
        *,
        user_id: int,
        platform: str,
        creator_id: str,
        submitted_url: str,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO creator_submissions (
                        user_id, platform, creator_id, submitted_url
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, platform, creator_id, submitted_url),
                )
                return int(cursor.fetchone()["id"])

    def list_entitlements(
        self,
        *,
        user_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM dataset_entitlements
                    WHERE user_id=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cursor.fetchall()
        return [dict(row) for row in rows]


    def list_users(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.*,
                        COALESCE(SUM(CASE WHEN c.bucket='free' THEN c.delta ELSE 0 END), 0)
                            AS free_credits,
                        COALESCE(SUM(CASE WHEN c.bucket='paid' THEN c.delta ELSE 0 END), 0)
                            AS paid_credits
                    FROM users u
                    LEFT JOIN credit_ledger c ON c.user_id=u.id
                    GROUP BY u.id
                    ORDER BY u.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def update_user_access(
        self,
        *,
        user_id: int,
        role: str | None = None,
        status: str | None = None,
    ) -> bool:
        if role is None and status is None:
            return False
        if role is not None and role not in {"admin", "member"}:
            raise ValueError("Role must be admin or member.")
        if status is not None and status not in {"active", "suspended"}:
            raise ValueError("Status must be active or suspended.")

        sets: list[str] = []
        params: list[Any] = []
        if role is not None:
            sets.append("role=%s")
            params.append(role)
        if status is not None:
            sets.append("status=%s")
            params.append(status)
        sets.append("updated_at=NOW()")
        params.append(user_id)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE users SET {', '.join(sets)} WHERE id=%s",
                    params,
                )
                return cursor.rowcount == 1

    def list_credit_ledger(
        self,
        *,
        user_id: int,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM credit_ledger
                    WHERE user_id=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def list_api_keys(
        self,
        *,
        user_id: int,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, name, key_prefix, last_used_at,
                           revoked_at, created_at
                    FROM api_keys
                    WHERE user_id=%s
                    ORDER BY id DESC
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def revoke_api_key(
        self,
        *,
        user_id: int,
        api_key_id: int,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE api_keys
                    SET revoked_at=NOW()
                    WHERE id=%s AND user_id=%s AND revoked_at IS NULL
                    """,
                    (api_key_id, user_id),
                )
                return cursor.rowcount == 1


    def apply_paid_credit_purchase(
        self,
        *,
        provider: str,
        event_id: str,
        user_id: int,
        credits: int,
        amount_minor: int | None,
        currency: str | None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if credits <= 0:
            raise ValueError("Purchased credits must be positive.")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE id=%s FOR UPDATE",
                    (user_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Unknown user.")

                cursor.execute(
                    """
                    INSERT INTO billing_events (
                        provider, event_id, user_id, event_type, status,
                        credits, amount_minor, currency, payload_json
                    ) VALUES (
                        %s, %s, %s, 'credit_purchase', 'completed',
                        %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT(provider, event_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        provider,
                        event_id,
                        user_id,
                        credits,
                        amount_minor,
                        currency,
                        json.dumps(payload or {}, ensure_ascii=False),
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        """
                        SELECT id
                        FROM billing_events
                        WHERE provider=%s AND event_id=%s
                        """,
                        (provider, event_id),
                    )
                    existing = cursor.fetchone()
                    applied = False
                    billing_event_id = int(existing["id"])
                else:
                    applied = True
                    billing_event_id = int(row["id"])
                    cursor.execute(
                        """
                        INSERT INTO credit_ledger (
                            user_id, bucket, delta, reason, reference_id
                        ) VALUES (%s, 'paid', %s, 'payment_purchase', %s)
                        """,
                        (user_id, credits, f"{provider}:{event_id}"),
                    )

                cursor.execute(
                    """
                    SELECT bucket, COALESCE(SUM(delta), 0) AS balance
                    FROM credit_ledger
                    WHERE user_id=%s
                    GROUP BY bucket
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        balances = {"free": 0, "paid": 0}
        for item in rows:
            balances[str(item["bucket"])] = int(item["balance"] or 0)
        balances["total"] = balances["free"] + balances["paid"]

        return {
            "billing_event_id": billing_event_id,
            "applied": applied,
            "credits": balances,
        }
