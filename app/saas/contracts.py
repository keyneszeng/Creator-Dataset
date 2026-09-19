from typing import Any, Protocol


class SaasRepository(Protocol):
    def create_user(
        self,
        *,
        email: str,
        display_name: str | None,
        role: str,
        free_credits: int,
    ) -> dict[str, Any]: ...

    def create_api_key(
        self,
        *,
        user_id: int,
        name: str,
        key_prefix: str,
        key_hash: str,
    ) -> int: ...

    def authenticate_api_key(
        self,
        *,
        key_hash: str,
    ) -> dict[str, Any] | None: ...

    def get_user(self, *, user_id: int) -> dict[str, Any] | None: ...

    def credit_balance(self, *, user_id: int) -> dict[str, int]: ...

    def grant_credits(
        self,
        *,
        user_id: int,
        bucket: str,
        amount: int,
        reason: str,
        reference_id: str | None = None,
    ) -> int: ...

    def unlock_dataset(
        self,
        *,
        user_id: int,
        platform: str,
        post_id: str,
        is_admin: bool,
    ) -> dict[str, Any]: ...

    def has_entitlement(
        self,
        *,
        user_id: int,
        platform: str,
        post_id: str,
        is_admin: bool,
    ) -> bool: ...

    def record_creator_submission(
        self,
        *,
        user_id: int,
        platform: str,
        creator_id: str,
        submitted_url: str,
    ) -> int: ...

    def list_entitlements(
        self,
        *,
        user_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def list_users(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    def update_user_access(
        self,
        *,
        user_id: int,
        role: str | None = None,
        status: str | None = None,
    ) -> bool: ...

    def list_credit_ledger(
        self,
        *,
        user_id: int,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...

    def list_api_keys(
        self,
        *,
        user_id: int,
    ) -> list[dict[str, Any]]: ...

    def revoke_api_key(
        self,
        *,
        user_id: int,
        api_key_id: int,
    ) -> bool: ...

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
    ) -> dict[str, Any]: ...
