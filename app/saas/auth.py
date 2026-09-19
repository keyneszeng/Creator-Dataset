from fastapi import Header, HTTPException

from app.core.settings import get_settings
from app.repositories.factory import create_saas_repository
from app.saas.models import Principal, UserRole
from app.saas.security import hash_api_key


def _extract_api_key(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if x_api_key:
        return x_api_key.strip()

    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()

    return None


def _authenticate(
    *,
    authorization: str | None,
    x_api_key: str | None,
) -> Principal:
    settings = get_settings()

    if not settings.saas_auth_enabled:
        return Principal(
            user_id=0,
            email="local-admin@localhost",
            role=UserRole.ADMIN,
        )

    secret = _extract_api_key(authorization, x_api_key)
    if not secret:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "message": "Provide Bearer token or X-API-Key.",
            },
        )

    row = create_saas_repository().authenticate_api_key(
        key_hash=hash_api_key(secret),
    )
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_API_KEY",
                "message": "API key is invalid or revoked.",
            },
        )

    try:
        role = UserRole(str(row["role"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "INVALID_ROLE",
                "message": "Account role is not recognized.",
            },
        ) from exc

    return Principal(
        user_id=int(row["user_id"]),
        email=str(row["email"]),
        role=role,
    )


def require_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    return _authenticate(
        authorization=authorization,
        x_api_key=x_api_key,
    )


def require_admin(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_bootstrap_key: str | None = Header(default=None),
) -> Principal:
    settings = get_settings()

    if (
        settings.saas_auth_enabled
        and settings.saas_bootstrap_admin_key
        and x_bootstrap_key
        and x_bootstrap_key == settings.saas_bootstrap_admin_key
    ):
        return Principal(
            user_id=0,
            email="bootstrap-admin@system",
            role=UserRole.ADMIN,
        )

    principal = _authenticate(
        authorization=authorization,
        x_api_key=x_api_key,
    )
    if not principal.is_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ADMIN_REQUIRED",
                "message": "Administrator permission is required.",
            },
        )
    return principal
