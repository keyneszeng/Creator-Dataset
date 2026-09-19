from typing import Any

from app.core.settings import get_settings
from app.repositories.factory import create_saas_repository
from app.saas.models import Principal
from app.saas.security import generate_api_key


class SaasService:
    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository or create_saas_repository()

    def create_user(
        self,
        *,
        email: str,
        display_name: str | None = None,
        role: str = "member",
    ) -> dict[str, Any]:
        if role not in {"admin", "member"}:
            raise ValueError("Role must be admin or member.")

        settings = get_settings()
        free_credits = (
            settings.saas_default_free_dataset_credits
            if role == "member"
            else 0
        )

        user = self.repository.create_user(
            email=email,
            display_name=display_name,
            role=role,
            free_credits=free_credits,
        )

        secret, prefix, digest = generate_api_key()
        self.repository.create_api_key(
            user_id=int(user["id"]),
            name="default",
            key_prefix=prefix,
            key_hash=digest,
        )

        return {
            "user": user,
            "api_key": secret,
            "api_key_prefix": prefix,
            "free_dataset_credits": free_credits,
        }

    def create_api_key(
        self,
        *,
        user_id: int,
        name: str,
    ) -> dict[str, Any]:
        user = self.repository.get_user(user_id=user_id)
        if user is None:
            raise ValueError("Unknown user.")

        secret, prefix, digest = generate_api_key()
        api_key_id = self.repository.create_api_key(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=digest,
        )
        return {
            "api_key_id": api_key_id,
            "api_key": secret,
            "api_key_prefix": prefix,
            "name": name,
        }

    def account(self, principal: Principal) -> dict[str, Any]:
        if principal.user_id == 0 and principal.is_admin:
            return {
                "user": {
                    "id": 0,
                    "email": principal.email,
                    "role": "admin",
                    "status": "active",
                },
                "credits": {
                    "free": 0,
                    "paid": 0,
                    "total": 0,
                    "unlimited": True,
                },
            }

        user = self.repository.get_user(user_id=principal.user_id)
        if user is None:
            raise ValueError("Unknown user.")

        return {
            "user": user,
            "credits": self.repository.credit_balance(
                user_id=principal.user_id
            ),
        }

    def unlock(
        self,
        *,
        principal: Principal,
        platform: str,
        post_id: str,
    ) -> dict[str, Any]:
        result = self.repository.unlock_dataset(
            user_id=principal.user_id,
            platform=platform,
            post_id=post_id,
            is_admin=principal.is_admin,
        )
        if principal.is_admin:
            result["credits"] = {
                "free": 0,
                "paid": 0,
                "total": 0,
                "unlimited": True,
            }
        else:
            result["credits"] = self.repository.credit_balance(
                user_id=principal.user_id
            )
        return result
