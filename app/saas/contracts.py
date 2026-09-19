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
