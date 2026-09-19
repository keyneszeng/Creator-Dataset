from typing import Any

from app.core.database import db_session


class SqliteSaasRepository:
    def create_user(
        self,
        *,
        email: str,
        display_name: str | None,
        role: str,
        free_credits: int,
    ) -> dict[str, Any]:
        normalized = email.strip().lower()
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (email, display_name, role)
                VALUES (?, ?, ?)
                """,
                (normalized, display_name, role),
            )
            user_id = int(cursor.lastrowid)
            if free_credits > 0:
                connection.execute(
                    """
                    INSERT INTO credit_ledger (
                        user_id, bucket, delta, reason, reference_id
                    ) VALUES (?, 'free', ?, 'signup_grant', NULL)
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
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO api_keys (
                    user_id, name, key_prefix, key_hash
                ) VALUES (?, ?, ?, ?)
                """,
                (user_id, name, key_prefix, key_hash),
            )
            return int(cursor.lastrowid)

    def authenticate_api_key(
        self,
        *,
        key_hash: str,
    ) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT u.id AS user_id, u.email, u.display_name,
                       u.role, u.status, k.id AS api_key_id,
                       k.key_prefix
                FROM api_keys k
                JOIN users u ON u.id=k.user_id
                WHERE k.key_hash=?
                  AND k.revoked_at IS NULL
                  AND u.status='active'
                LIMIT 1
                """,
                (key_hash,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE api_keys SET last_used_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["api_key_id"],),
            )
        return dict(row)

    def get_user(self, *, user_id: int) -> dict[str, Any] | None:
        with db_session() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def credit_balance(self, *, user_id: int) -> dict[str, int]:
        with db_session() as connection:
            rows = connection.execute(
                """
                SELECT bucket, COALESCE(SUM(delta), 0) AS balance
                FROM credit_ledger
                WHERE user_id=?
                GROUP BY bucket
                """,
                (user_id,),
            ).fetchall()
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
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO credit_ledger (
                    user_id, bucket, delta, reason, reference_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, bucket, amount, reason, reference_id),
            )
            return int(cursor.lastrowid)

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

        with db_session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            user = connection.execute(
                "SELECT id FROM users WHERE id=? AND status='active'",
                (user_id,),
            ).fetchone()
            if user is None:
                raise ValueError("Unknown or inactive user.")

            existing = connection.execute(
                """
                SELECT source, granted_at
                FROM dataset_entitlements
                WHERE user_id=? AND platform=? AND post_id=?
                """,
                (user_id, platform, post_id),
            ).fetchone()
            if existing:
                return {
                    "allowed": True,
                    "charged": False,
                    "source": str(existing["source"]),
                    "post_id": post_id,
                }

            balances = {"free": 0, "paid": 0}
            rows = connection.execute(
                """
                SELECT bucket, COALESCE(SUM(delta), 0) AS balance
                FROM credit_ledger
                WHERE user_id=?
                GROUP BY bucket
                """,
                (user_id,),
            ).fetchall()
            for row in rows:
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

            connection.execute(
                """
                INSERT INTO dataset_entitlements (
                    user_id, platform, post_id, source
                ) VALUES (?, ?, ?, ?)
                """,
                (user_id, platform, post_id, source),
            )
            connection.execute(
                """
                INSERT INTO credit_ledger (
                    user_id, bucket, delta, reason, reference_id
                ) VALUES (?, ?, -1, 'dataset_unlock', ?)
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
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM dataset_entitlements
                WHERE user_id=? AND platform=? AND post_id=?
                  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                LIMIT 1
                """,
                (user_id, platform, post_id),
            ).fetchone()
        return row is not None

    def record_creator_submission(
        self,
        *,
        user_id: int,
        platform: str,
        creator_id: str,
        submitted_url: str,
    ) -> int:
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO creator_submissions (
                    user_id, platform, creator_id, submitted_url
                ) VALUES (?, ?, ?, ?)
                """,
                (user_id, platform, creator_id, submitted_url),
            )
            return int(cursor.lastrowid)

    def list_entitlements(
        self,
        *,
        user_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with db_session() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM dataset_entitlements
                WHERE user_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
