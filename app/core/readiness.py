import tempfile
from pathlib import Path
from uuid import uuid4

from app.core.database import db_session
from app.core.migrations import CURRENT_SCHEMA_VERSION
from app.core.settings import get_settings
from app.postgres.database import (
    POSTGRES_SCHEMA_VERSION,
    connect_postgres,
)
from app.storage.factory import create_object_store


def check_readiness(*, deep_storage: bool = False) -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, object] = {}
    ready = True

    try:
        if settings.database_backend == "sqlite":
            with db_session() as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) AS version "
                    "FROM schema_migrations"
                ).fetchone()
                version = int(row["version"])
                connection.execute("SELECT 1").fetchone()
            expected = CURRENT_SCHEMA_VERSION
        else:
            with connect_postgres(str(settings.database_url)) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT COALESCE(MAX(version), 0) AS version "
                        "FROM schema_migrations"
                    )
                    version = int(cursor.fetchone()["version"])
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            expected = POSTGRES_SCHEMA_VERSION

        db_ok = version == expected
        checks["database"] = {
            "ok": db_ok,
            "backend": settings.database_backend,
            "schema_version": version,
            "expected_schema_version": expected,
        }
        ready = ready and db_ok
    except Exception as exc:
        checks["database"] = {
            "ok": False,
            "backend": settings.database_backend,
            "error": str(exc),
        }
        ready = False

    production = str(settings.environment).lower() == "production"
    saas_auth_ok = (not production) or bool(settings.saas_auth_enabled)
    checks["saas_security"] = {
        "ok": saas_auth_ok,
        "environment": settings.environment,
        "auth_enabled": bool(settings.saas_auth_enabled),
        "bootstrap_key_configured": bool(
            settings.saas_bootstrap_admin_key
        ),
        "message": (
            "Production requires SaaS authentication."
            if not saas_auth_ok
            else "SaaS authentication configuration is acceptable."
        ),
    }
    ready = ready and saas_auth_ok

    llm_key_ok = (
        (not settings.llm_enabled)
        or bool(settings.llm_credential_encryption_key)
    )
    llm_host_ok = (
        (not settings.llm_enabled)
        or settings.deployment_mode == "local"
        or bool(settings.llm_allowed_hosts.strip())
    )
    llm_ok = llm_key_ok and llm_host_ok
    checks["llm_security"] = {
        "ok": llm_ok,
        "enabled": bool(settings.llm_enabled),
        "credential_encryption_key_configured": bool(
            settings.llm_credential_encryption_key
        ),
        "allowed_hosts_configured": bool(
            settings.llm_allowed_hosts.strip()
        ),
        "message": (
            "LLM configuration is acceptable."
            if llm_ok
            else (
                "Enabled LLM support requires a credential encryption key "
                "and cloud deployments require an endpoint allow-list."
            )
        ),
    }
    ready = ready and llm_ok

    checks["storage"] = {
        "ok": True,
        "backend": settings.storage_backend,
        "deep_checked": deep_storage,
    }

    if deep_storage:
        key = f"_health/{uuid4().hex}.txt"
        try:
            store = create_object_store()
            with tempfile.NamedTemporaryFile(delete=False) as handle:
                source = Path(handle.name)
                handle.write(b"creator-dataset-readiness")
            try:
                stored = store.put_file(source, key=key)
                with store.materialize(key=stored.key, suffix=".txt") as path:
                    payload = path.read_bytes()
                if payload != b"creator-dataset-readiness":
                    raise ValueError(
                        "Object storage roundtrip payload mismatch."
                    )
                store.delete(key=stored.key)
                checks["storage"] = {
                    "ok": True,
                    "backend": stored.backend,
                    "deep_checked": True,
                }
            finally:
                source.unlink(missing_ok=True)
        except Exception as exc:
            checks["storage"] = {
                "ok": False,
                "backend": settings.storage_backend,
                "deep_checked": True,
                "error": str(exc),
            }
            ready = False

    return {
        "ready": ready,
        "deployment_mode": settings.deployment_mode,
        "checks": checks,
    }
